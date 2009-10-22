import os
import sys
import logging
from datetime import datetime

log = logging.getLogger('manager')

from flexget.plugin import plugins

import yaml
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
Session = sessionmaker()

from sqlalchemy import Column, Integer, String, DateTime

class FailedEntry(Base):
    __tablename__ =  'failed'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)
    tof = Column(DateTime, default=datetime.now())

    def __init__(self, title, url):
        self.title = title
        self.url = url

    def __str__(self):
        return '<Failed(title=%s)>' % (self.title)

class Manager:
    unit_test = False
    options = None
    
    def __init__(self, options):
        self.options = options
        self.config_base = None
        self.config_name = None
        self.db_filename = None
        self.engine = None
        self.lockfile = None

        self.config = {}
        self.feeds = {}
        
        # shelve
        self.shelve_session = None

        self.initialize()
            
        if self.options.log_start:
            logging.info('FlexGet started')

        log.debug('Default encoding: %s' % sys.getdefaultencoding())

    def initialize(self):
        """Separated from __init__ so that unit tests can modify options before loading config."""
        self.load_config()
        self.init_sqlalchemy()
        
    def load_config(self):
        """Load the configuration file"""
        startup_path = os.path.dirname(os.path.abspath(sys.path[0]))
        home_path = os.path.join(os.path.expanduser('~'), '.flexget')
        current_path = os.getcwd()
        exec_path = sys.path[0]
        
        possible = {}
        possible[os.path.join(startup_path, self.options.config)] = startup_path
        possible[os.path.join(home_path, self.options.config)] = home_path
        # for virtualenv / dev sandbox
        possible[os.path.join(sys.path[0], '..', self.options.config)] = os.path.join(sys.path[0], '..')
        possible[os.path.join(current_path, self.options.config)] = current_path
        possible[os.path.join(exec_path, self.options.config)] = exec_path
        
        for config, base in possible.iteritems():
            if os.path.exists(config):
                self.pre_check_config(config)
                try:
                    self.config = yaml.safe_load(file(config))
                except Exception, e:
                    log.critical(e)
                    print ''
                    print '-'*79
                    print ' This is caused by malformed configuration file, common reasons:'
                    print '-'*79
                    print ''
                    print ' o Indentation error'
                    print ' o Missing : from end of the line'
                    print ' o Non ASCII characters (use UTF8)'
                    print ' o If text contains : or [] characters it must be quoted\n'
                    try:
                        if not e.context_mark is None:
                            area = str(e.context_mark)[str(e.context_mark).find('line'):]
                            print ' Check your configuration near %s' % area
                            print ' Fault is almost always in this line or previous\n'
                    except:
                        pass
                    sys.exit(1)
                # config loaded successfully
                self.config_name = os.path.splitext(os.path.basename(config))[0]
                self.config_base = base
                return
        log.info('Tried to read from: %s' % ', '.join(possible))
        raise IOError('Failed to find configuration file %s' % self.options.config)
    
    def pre_check_config(self, fn):
        """
            Checks configuration file for common mistakes that are easily detectable 
        """
        
        def get_indentation(line):
            i, n = 0, len(line)
            while i < n and line[i] == " ":
                i += 1
            return i
                
        def isodd(n):
            return bool(n%2)
        
        file = open(fn)
        line_num = 0
        # flags
        prev_indentation = 0
        prev_mapping = False
        prev_list = True
        for line in file:
            line_num += 1
            # remove linefeed
            line = line[:-1]
            # empty line
            if line.strip()=='':
                continue
            # comment line
            if line[0]=='#':
                continue
            indentation = get_indentation(line)
            
            #print '%i - %i: %s' % (line_num, indentation, line)
            #print 'prev_mapping: %s, prev_list: %s, prev_ind: %s' % (prev_mapping, prev_list, prev_indentation)
            
            if isodd(indentation):
                log.warning('Config line %s has odd (uneven) indentation' % line_num)
            if indentation > prev_indentation + 2 and not prev_mapping:
                # line increases indentation but previously didn't start mapping
                log.warning('Config line %s is likely missing ":" at the end' % (line_num - 1))
            if indentation > prev_indentation + 2 and prev_mapping and not prev_list:
                # mapping value after non list indented more than 2
                log.warning('Config line %s is indented too much' % line_num)
            if indentation < prev_indentation + 2 and prev_mapping and prev_list:
                log.warning('Config line %s is not indented enough' % line_num)
            if prev_mapping and indentation <= prev_indentation:
                # after opening a map, indentation decreases
                log.warning('Config line %s is indented incorrectly (previous line ends with ":")' % line_num)
            if prev_list and not prev_mapping and indentation > prev_indentation:
                # after a list item that does NOT start mapping indentation increases
                log.warning('Config line %s is likely missing ":" at the end' % (line_num - 1))
                
            prev_indentation = indentation
            # this line is a mapping (ends with :)
            prev_mapping = line[-1] == ':'
            # this line is a list
            prev_list = line.strip()[0] == '-'
            
        file.close()

    def init_sqlalchemy(self):
        """Initialize SQLAlchemy"""
        import shutil
        
        # load old shelve session
        if self.options.migrate:
            shelve_session_name = self.options.migrate
        else:
            shelve_session_name = os.path.join(self.config_base, 'session-%s.db' % self.config_name)
        if os.path.exists(shelve_session_name):
            import shelve
            import copy
            log.critical('Old shelve session found, relevant data will be migrated.')
            old = shelve.open(shelve_session_name, flag='r', protocol=2)
            self.shelve_session = copy.deepcopy(old['cache'])
            old.close()
            if not self.options.test:
                shutil.move(shelve_session_name, '%s_migrated' % shelve_session_name)
        
        # SQLAlchemy
        if self.unit_test:
            connection = 'sqlite:///:memory:'
        else:
            self.db_filename = os.path.join(self.config_base, 'db-%s.sqlite' % self.config_name)
            if self.options.test:
                db_test_filename = os.path.join(self.config_base, 'test-%s.sqlite' % self.config_name)
                log.info('Test mode, creating a copy from database.')
                if os.path.exists(self.db_filename):
                    shutil.copy(self.db_filename, db_test_filename)
                self.db_filename = db_test_filename 
            
            # in case running on windows, needs double \\
            filename = self.db_filename.replace('\\', '\\\\')
            connection = 'sqlite:///%s' % filename
        
        # fire up the engine
        log.debug('connection: %s' % connection)
        try:
            self.engine = sqlalchemy.create_engine(connection, echo=self.options.debug_sql)
        except ImportError, e:
            log.critical('Unable to use SQLite. Try installing python SQLite packages.')
            log.exception(e)
            sys.exit(1)
        Session.configure(bind=self.engine)
        # create all tables
        if self.options.reset:
            Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        
        
    def acquire_lock(self):
        self.lockfile = os.path.join(self.config_base, ".%s-lock" % self.config_name)
        if os.path.exists(self.lockfile):
            f = file(self.lockfile)
            pid = f.read()
            f.close()
            print "Another process (%s) is running, will exit." % pid.strip()
            print "If you're sure there is no other instance running, delete %s" % self.lockfile
            sys.exit(1)
        
        f = file(self.lockfile, 'w')
        f.write("PID: %s\n" % os.getpid())
        f.close()
        
    def release_lock(self):
        os.remove(self.lockfile)

    def print_failed(self):
        """Parameter --failed"""
        
        failed = Session()
        results = failed.query(FailedEntry).all()
        if not results:
            print 'No failed entries recorded'
        for entry in results:
            print '%16s - %s' % (entry.tof.strftime('%Y-%m-%d %H:%M'), entry.title)
        failed.close()

    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        failed = Session()
        failedentry = FailedEntry(str(entry['title']), str(entry['url']))
        # TODO: query item's existence
        if not failed.query(FailedEntry).filter(FailedEntry.title==str(entry['title'])).first():
            failed.add(failedentry)
        # TODO: limit item number to 25
        i = 0
        for row in failed.query(FailedEntry).order_by(FailedEntry.tof.desc()).all():
            i += 1
            if (i > 25):
                failed.delete(row)
        failed.commit()
        failed.close()
            
    def clear_failed(self):
        """Clears list of failed entries"""
        session = Session()
        results = session.query(FailedEntry).all()
        for row in results:
            session.delete(row)
        print 'Cleared %i items.' % len(results)
        session.commit()
        session.close()
                
    def create_feeds(self):
        """Creates instances of all configured feeds"""
        from flexget.feed import Feed

        # construct feed list
        feeds = self.config.get('feeds', {}).keys()
        if not feeds: 
            log.critical('There are no feeds in the configuration file!')

        for name in feeds:
            # validate (TODO: make use of validator?)
            if not isinstance(self.config['feeds'][name], dict):
                if isinstance(self.config['feeds'][name], str):
                    if name in plugins:
                        log.error('\'%s\' is known keyword, but in wrong indentation level. \
                        Please indent it correctly under feed, it should have 2 more spaces \
                        than feed name.' % name)
                        continue
                log.error('\'%s\' is not a properly configured feed, please check indentation levels.' % name)
                continue
            
            # create feed
            feed = Feed(self, name, self.config['feeds'][name])
            # if feed name is prefixed with _ it's disabled
            if name.startswith('_'):
                feed.enabled = False
            # if executing only one feed, disable others
            if self.options.onlyfeed:
                if name.lower() != self.options.onlyfeed.lower():
                    feed.enabled = False
            self.feeds[name] = feed
        
        if self.options.onlyfeed:
            if not [feed for feed in self.feeds.itervalues() if feed.enabled]:
                log.critical('Could not find feed %s' % self.options.onlyfeed)
                
    def disable_feeds(self):
        """Disable all feeds."""
        for feed in self.feeds.itervalues():
            feed.enabled = False
            
    def enable_feeds(self):
        """Enable all feeds."""
        for feed in self.feeds.itervalues():
            feed.enabled = True

    def execute(self):
        """Iterate trough all feeds and run them."""

        if not self.config:
            log.critical('Configuration file is empty.')
            return
        
        # separated for future when flexget runs continously in the background
        self.create_feeds()

        failed = []

        # execute process_start to all feeds
        for name, feed in self.feeds.iteritems():
            if not feed.enabled: 
                continue
            try:
                log.log(5, 'calling process_start on a feed %s' % name)
                feed.process_start()
            except Exception, e:
                failed.append(name)
                log.exception('Feed %s process_start: %s' % (feed.name, e))

        for name, feed in self.feeds.iteritems():
            if not feed.enabled: 
                continue
            if name in failed:
                continue
            try:
                feed.session = Session()
                feed.execute()
                feed.session.commit()
            except Exception, e:
                failed.append(name)
                log.exception('Feed %s: %s' % (feed.name, e))
            except KeyboardInterrupt:
                # show real stack trace in debug mode
                if self.options.debug:
                    raise
                print '**** Keyboard Interrupt ****'
                return
            finally:
                # note: will perform rollback if error occured (session has not been committed)
                feed.session.close()

        # execute process_end to all feeds
        for name, feed in self.feeds.iteritems():
            if not feed.enabled: 
                continue
            if name in failed:
                continue
            try:
                feed.process_end()
            except Exception, e:
                log.exception('Feed %s process_end: %s' % (name, e))
                
    def shutdown(self):
        """Application is being exited"""
        
        # remove temporary database used in test mode
        if self.options.test:
            if not 'test' in self.db_filename:
                raise Exception('trying to delete non test database?')
            os.remove(self.db_filename)
            log.info('Removed test database') 

        self.release_lock()