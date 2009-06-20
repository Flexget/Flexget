import os, os.path
import sys
import logging
import logging.handlers
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
    configname = None
    options = None
    
    def __init__(self, options, config_base):
        self.options = options
        self.config_base = config_base

        self.config = {}
        self.feeds = {}
        
        # shelve
        self.shelve_session = None

        self.initialize()
            
        if self.options.log_start:
            logging.info('FlexGet started')

        log.debug('Default encoding: %s' % sys.getdefaultencoding())

    def initialize(self):
        """Separated from __init__ so that unit test can modify options before loading config."""
        try:
            self.load_config()
        except Exception, e:
            log.critical(e)
            sys.exit(1)
            
        self.init_sqlalchemy()
        
    def load_config(self):
        """Load the configuration file"""
        possible = [os.path.join(self.config_base, self.options.config), self.options.config]
        for config in possible:
            if os.path.exists(config):
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
                    print ' o If text contains : it must be quoted\n'
                    area = str(e.context_mark)[str(e.context_mark).find('line'):]
                    print ' Check your configuration near %s' % area
                    print ' Fault is almost always in this line or previous\n'
                    sys.exit(1)
                self.configname = os.path.basename(config)[:-4]
                return
        log.debug('Tried to read from: %s' % ', '.join(possible))
        raise Exception('Failed to find configuration file %s' % self.options.config)

    def init_sqlalchemy(self):
        """Initialize SQLAlchemy"""
        import shutil
        
        # load old shelve session
        if self.options.migrate:
            shelve_session_name = self.options.migrate
        else:
            shelve_session_name = os.path.join(self.config_base, 'session-%s.db' % self.configname)
        if os.path.exists(shelve_session_name):
            import shelve
            import copy
            log.critical('Old shelve session found, relevant data will be migrated.')
            old = shelve.open(shelve_session_name, flag='r', protocol=2)
            self.shelve_session = copy.deepcopy(old['cache'])
            old.close()
            shutil.move(shelve_session_name, '%s_migrated' % shelve_session_name)
        
        # SQLAlchemy
        self.db_filename = os.path.join(self.config_base, 'db-%s.sqlite' % self.configname)
        
        if self.options.test:
            db_test_filename = os.path.join(self.config_base, 'test-%s.sqlite' % self.configname)
            log.info('Test mode, creating a copy from database.')
            if os.path.exists(self.db_filename):
                shutil.copy(self.db_filename, db_test_filename)
            self.db_filename = db_test_filename 
        
        # in case running on windows, needs double \\
        filename = self.db_filename.replace('\\', '\\\\')

        connection = 'sqlite:///%s' % filename
        log.debug('connection: %s' % connection)
        try:
            engine = sqlalchemy.create_engine(connection, echo=self.options.debug_sql)
        except ImportError, e:
            log.critical('Unable to use SQLite. Try installing python SQLite packages.')
            log.exception(e)
            sys.exit(1)
        Session.configure(bind=engine)
        # create all tables
        if self.options.reset:
            Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

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
        #TODO: query item's existence
        if not failed.query(FailedEntry).filter(FailedEntry.title==str(entry['title'])).first():
            failed.add(failedentry)
        #TODO: limit item number to 25
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
