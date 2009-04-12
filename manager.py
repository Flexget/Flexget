import os, os.path
import sys
import logging
import logging.handlers
import time

log = logging.getLogger('manager')

try:
    from optparse import OptionParser, SUPPRESS_HELP
except ImportError:
    print 'Please install Optik 1.4.1 (or higher) or preferably update your Python'
    sys.exit(1)

try:
    import sqlalchemy
    if float(sqlalchemy.__version__[0:3]) < 0.5:
        raise ImportError('Old SQLAlchemy')
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import declarative_base
except ImportError:
    print 'Please install SQLAlchemy (>0.5) from http://www.sqlalchemy.org/ or from your distro repository'
    sys.exit(1)

try:
    import yaml
except ImportError:
    print 'Please install PyYAML from http://pyyaml.org/wiki/PyYAML or from your distro repository'
    sys.exit(1)

class RegisterException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class ModuleWarning(Warning):
    def __init__(self, value, logger=logging, **kwargs):
        self.value = value
        self.log = logger
        self.kwargs = kwargs
    def __str__(self):
        return self.value
        
class MergeException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

Base = declarative_base()
Session = sessionmaker()

class Manager:

    log_initialized = False
    
    def __init__(self, unit_test=False):
        self.init_logging()
    
        self.unit_test = unit_test
        self.configname = None
        self.options = None
        self.modules = {}
        self.config = {}
        
        # events
        self.events = ['start', 'input', 'filter', 'download', 'modify', 'output', 'exit']
        self.event_methods = {'start':'feed_start', 'input':'feed_input', 'filter':
                              'feed_filter', 'download':'feed_download', 'modify':'feed_modify', 
                              'output':'feed_output', 'exit':'feed_exit', 'abort':'feed_abort',
                              'terminate':'application_terminate'}
        
        # pass current module instance around while loading
        self.__instance = False
        self.__class_name = None
        self.__load_queue = self.events + ['module', 'source']
        self.__event_queue = {}

        # settings
        self.moduledir = os.path.join(sys.path[0], 'modules')
        
        # shelve
        self.shelve_session = None

        # initialize commandline options
        parser = OptionParser()
        parser.add_option('--log-start', action='store_true', dest='log_start', default=0,
                          help='Add FlexGet executions into a log.')
        parser.add_option('--test', action='store_true', dest='test', default=0,
                          help='Verbose what would happend on normal execution.')
        parser.add_option('--check', action='store_true', dest='validate', default=0,
                          help='Validate configuration file and print errors.')
        parser.add_option('--learn', action='store_true', dest='learn', default=0,
                          help='Matches are not downloaded but will be skipped in the future.')
        parser.add_option('--feed', action='store', dest='onlyfeed', default=None,
                          help='Run only specified feed from config.')
        parser.add_option('--no-cache', action='store_true', dest='nocache', default=0,
                          help='Disable caches. Works only in modules that have explicit support.')
        parser.add_option('--reset', action='store_true', dest='reset', default=0,
                          help='Forgets everything that has been done and learns current matches.')
        parser.add_option('--doc', action='store', dest='doc',
                          help='Display module documentation (example: --doc patterns). See --list.')
        parser.add_option('--list', action='store_true', dest='list', default=0,
                          help='List all available modules.')
        parser.add_option('--failed', action='store_true', dest='failed', default=0,
                          help='List recently failed entries.')
        parser.add_option('--clear', action='store_true', dest='clear_failed', default=0,
                          help='Clear recently failed list.')
        parser.add_option('-c', action='store', dest='config', default='config.yml',
                          help='Specify configuration file. Default is config.yml')
        parser.add_option('-d', action='store_true', dest='details', default=0,
                          help='Display detailed process information.')
        parser.add_option('--cron', action='store_true', dest='quiet', default=0,
                          help='Disables stdout and stderr output, log file used. Reduces logging level slightly.')
        parser.add_option('--experimental', action='store_true', dest='experimental', default=0,
                          help=SUPPRESS_HELP)
        parser.add_option('--debug', action='store_true', dest='debug', default=False,
                          help=SUPPRESS_HELP)
        parser.add_option('--debug-sql', action='store_true', dest='debug_sql', default=False,
                          help=SUPPRESS_HELP)
        parser.add_option('--validate', action='store_true', dest='validate', default=0,
                          help=SUPPRESS_HELP)
        parser.add_option('--verbosity', action='store_true', dest='crap', default=0,
                          help=SUPPRESS_HELP)
        # provides backward compatibility to --cron
        parser.add_option('-q', action='store_true', dest='quiet', default=0,
                          help=SUPPRESS_HELP)
        # hacky way to allow unit tests to use --online parameter, without this Optik would exit application ...
        parser.add_option('--online', action='store_true', dest='unittest_online', default=0,
                          help=SUPPRESS_HELP)

        # add module path to sys.path so that imports work properly ..
        sys.path.append(self.moduledir)
        sys.path.insert(1, os.path.join(sys.path[0], 'BeautifulSoup-3.0.7a'))

        # load modules, modules may add more commandline parameters!
        start_time = time.clock()
        self.load_modules(parser, self.moduledir)
        took = time.clock() - start_time
        log.debug('load_modules took %.2f seconds' % took)

        # parse options including module customized options
        self.options = parser.parse_args()[0]
        
        # perform commandline sanity check(s)
        if self.options.test and self.options.learn:
            parser.error('--test and --learn are mutually exclusive')
            
        if self.options.log_start:
            logging.info('FlexGet started')
            
        # reset is executed with learn
        if self.options.reset:
            self.options.learn = True
            
        if not self.unit_test:
            self.initialize()
            
        # TODO: xxx
        if self.options.test:
            print '--test is borked again'
            sys.exit(1)

    def initialize(self):
        """Separated from __init__ so that unit test can modify options before loading config."""
        try:
            self.load_config()
        except Exception, e:
            log.critical(e)
            sys.exit(1)
            
        self.init_sqlalchemy()
        log.debug('Default encoding: %s' % sys.getdefaultencoding())
        
    def init_logging(self):
        """Creates and initializes logger."""
        
        if Manager.log_initialized: 
            return
        
        filename = os.path.join(sys.path[0], 'flexget.log')

        # get root logger
        logger = logging.getLogger()
        handler = logging.handlers.RotatingFileHandler(filename, maxBytes=200*1024, backupCount=9)
        # time format is same format of strftime
        formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s %(name)-11s %(message)s', '%Y-%m-%d %H:%M')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # unfortunately we cannot use optik in here
        if '--debug' in sys.argv:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        # log to console, unless --cron present (or -q)
        if not '-q' in sys.argv and not '--cron' in sys.argv:
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            logger.addHandler(console)
        
        Manager.log_initialized = True
           
    def load_config(self):
        """Load the configuration file"""
        possible = [os.path.join(sys.path[0], self.options.config), self.options.config]
        for config in possible:
            if os.path.exists(config):
                self.config = yaml.safe_load(file(config))
                self.configname = os.path.basename(config)[:-4]
                return
        log.debug('Tried to read from: %s' % ', '.join(possible, ', '))
        raise Exception('Failed to load configuration file %s' % self.options.config)

    def init_sqlalchemy(self):
        """Initialize SQLAlchemy"""
        
        # load old shelve session
        shelve_session_name = os.path.join(sys.path[0], 'session-%s.db' % self.configname)
        if os.path.exists(shelve_session_name):
            import shelve
            import copy
            import shutil
            log.critical('Old shelve session found, relevant data will be migrated.')
            old = shelve.open(shelve_session_name, flag='r', protocol=2)
            self.shelve_session = copy.deepcopy(old['cache'])
            old.close()
            shutil.move(shelve_session_name, '%s_migrated' % shelve_session_name)
        
        # SQLAlchemy
        engine = sqlalchemy.create_engine('sqlite:////%s/db-%s.sqlite' %( sys.path[0], self.configname), echo=self.options.debug_sql)
        Session.configure(bind=engine)
        # create all tables
        if self.options.reset:
            Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    # TODO: move into utils?! used only by couple times in modules anymore ...
    def sanitize(self, d):
        """Makes dictionary d contain only yaml.safe_dump compatible elements"""
        import types
        valid = [types.DictType, types.IntType, types.NoneType,
                 types.StringType, types.UnicodeType, types.BooleanType,
                 types.ListType, types.LongType, types.FloatType]
        for k in d.keys():
            if type(d[k])==types.ListType:
                for i in d[k][:]:
                    if not type(i) in valid:
                        log.debug('Removed non yaml compatible list item from key %s %s' % (k, type([k])))
                        d[k].remove(i)
            if type(d[k])==types.DictType:
                self.sanitize(d[k])
            if not type(d[k]) in valid:
                log.debug('Removed non yaml compatible key %s %s' % (k, type(d[k])))
                d.pop(k)

    def load_modules(self, parser, moduledir):
        """Load all modules from moduledir"""
        loaded = {} # prevent modules being loaded multiple times when they're imported by other modules
        
        # ----------------------------------------------------------------------------------------------
        # TODO: HACK! Loading method tries to instantiate SQLAlchemy func since it has register method!
        # ----------------------------------------------------------------------------------------------
        loaded['func'] = True
        
        for prefix in self.__load_queue:
            for module in self.find_modules(moduledir, prefix):
                log.debug('loading module %s' % module)
                try:
                    module = __import__(module)
                except Exception, e:
                    log.critical('Module %s is faulty! Ignored!' % module)
                    log.exception(e)
                    continue
                for name, item in vars(module).iteritems():
                    if loaded.get(name, False): 
                        continue
                    if hasattr(item, 'register'):
                        try:
                            instance = item()
                            # store current module instance so register method may access it
                            # without modules having to explicitly give it as parameter
                            self.__instance = instance
                            self.__class_name = name
                        except:
                            log.exception('Exception occurred while creating instance %s' % name)
                            return
                        method = getattr(instance, 'register', None)
                        if callable(method):
                            try:
                                method(self, parser)
                                loaded[name] = True
                            except RegisterException, e:
                                log.critical('Error while registering module %s. %s' % (name, e.value))
                            except TypeError, e:
                                log.critical('Module %s register method has invalid signature!' % name)
                                log.exception(e)
                        else:
                            log.critical('Module %s register method is not callable' % name)
        
        # check that event queue is empty (all module created events succeeded)
        if self.__event_queue:
            for event, info in self.__event_queue.iteritems():
                log.error('Module %s requested new event %s, but it could not be created at requested \
                point (before, after). Module is not working properly.' % (info['class_name'], event))

    def find_modules(self, directory, prefix):
        """Return array containing all modules in passed path that begin with prefix."""
        modules = []
        for fn in os.listdir(directory):
            if fn.startswith(prefix+'_') and fn.endswith('.py'):
                modules.append(fn[:-3])
        return modules

    def get_settings(self, keyword, defaults={}):
        # TO BE REMOVED
        """
            Return defaults / settings for a keyword. Optionally you may pass defaults values in dictionary 
            which will be used as default values.

            Ie. Passed defaults:
            {'size': 20, 'length': 30}
            User has configured:
            {'length': 40}
            Returned:
            {'size': 20, 'length': 40}

            See. http://flexget.com/wiki/GlobalSection - uses same merge
        """
        settings = self.config.get('settings', {})
        config = settings.get(keyword, {})
        self.merge_dict_from_to(config, defaults)
        return defaults

    def register(self, name, **kwargs):
        """
            Register module with name.

            **kwargs options:
            
            builtin : boolean
            <event>_priority : int
            group - str
            groups - list of groups (str)
            
            Modules may also pass any number of additional values to be stored in module info (dict).
            
        """
        if name in self.modules:
            raise RegisterException('Module %s is already registered' % name)
        info = kwargs
        info['instance'] = self.__instance
        info['name'] = name
        info.setdefault('events', False)   # module has events
        info.setdefault('builtin', False)
        # probulate module
        for event, method in self.event_methods.iteritems():
            if hasattr(info['instance'], method):
                if callable(getattr(info['instance'], method)):
                    info['events'] = True
        # parse event priorities, given in form <event>_priority=<n>, ie. input_priority=10
        for event in self.events:
            key = '%s_priority' % event
            if key in info:
                info.setdefault('priorities', {})
                info['priorities'][event] = info[key]
                del(info[key])
                
        self.modules[name] = info
        
    def add_feed_event(self, event_name, **kwargs):
        """Register new event in FlexGet and queue module loading for them. 
        Note: queue works only while loading is in process."""
        
        if 'before' in kwargs and 'after' in kwargs:
            raise RegisterException('You can only give either before or after for a event.')
        if not 'before' in kwargs and not 'after' in kwargs:
            raise RegisterException('You must specify either a before or after event.')
        if event_name in self.events or event_name in self.__event_queue:
            raise RegisterException('Event %s already exists.' % event_name)

        def add_event(name, args):
            if 'before' in args:
                if not args.get('before', None) in self.events:
                    return False
            if 'after' in args:
                if not args.get('after', None) in self.events:
                    return False
            # add method name to event -> method lookup table
            self.event_methods[name] = 'feed_'+name
            # queue module loading for this type
            self.__load_queue.append(event_name)
            # place event in event list
            if args.get('after'):
                self.events.insert(self.events.index(kwargs['after'])+1, name)
            if args.get('before'):
                self.events.insert(self.events.index(kwargs['before']), name)
            return True

        kwargs.setdefault('class_name', self.__class_name)
        if not add_event(event_name, kwargs):
            # specified event insert point does not exists yet, add into queue and exit
            self.__event_queue[event_name] = kwargs
            return

        # new event added, now loop and see if any queued can be added after this
        for event_name, kwargs in self.__event_queue.items():
            if add_event(event_name, kwargs):
                del self.__event_queue[event_name]

    def get_modules_by_event(self, event):
        """Return all modules that hook event in order of priority."""
        modules = []
        if not event in self.event_methods:
            raise Exception('Unknown event %s' % event)
        method = self.event_methods[event]
        for _, info in self.modules.iteritems():
            instance = info['instance']
            if not hasattr(instance, method):
                continue
            if callable(getattr(instance, method)):
                modules.append(info)
        modules.sort(lambda x, y: cmp(x.get('priorities', {}).get(event, 0), \
                                      y.get('priorities', {}).get(event, 0)))
        xx = []
        for m in modules:
            if 'priorities' in m:
                if event in m['priorities']:
                    xx.append(str(m['priorities'][event]))
        #print ', '.join(xx)
        
        return modules

    def get_modules_by_group(self, group):
        """Return all modules with in specified group."""
        res = []
        for _, info in self.modules.iteritems():
            if info.get('group', '')==group or group in info.get('groups', []):
                res.append(info)
        return res
        
    def get_module_by_name(self, name):
        """Get module by name, prefered way since manager.modules structure may be changed at some point."""
        if not name in self.modules:
            raise Exception('Unknown module %s' % name)
        return self.modules[name]

    def print_module_list(self):
        # TODO: rewrite!
        """Parameter --list"""
        print '-'*60
        print '%-20s%-30s%s' % ('Keyword', 'Roles', '--doc')
        print '-'*60
        modules = []
        roles = {}
        for event in self.events:
            try:
                ml = self.get_modules_by_event(event)
            except:
                continue
            for m in ml:
                dupe = False
                for module in modules:
                    if module['name'] == m['name']: 
                        dupe = True
                if not dupe:
                    modules.append(m)
            # build roles list
            for m in ml:
                if m['name'] in roles:
                    roles[m['name']].append(event)
                else:
                    roles[m['name']] = [event]
        for module in modules:
            # do not include test classes, unless in debug mode
            if module.get('debug_module', False) and not self.options.debug:
                continue
            doc = 'Yes'
            if not module['instance'].__doc__: 
                doc = 'No'
            print '%-20s%-30s%s' % (module['name'], ', '.join(roles[module['name']]), doc)
        print '-'*60

    def print_module_doc(self):
        """Parameter --doc <keyword>"""
        keyword = self.options.doc
        found = False
        module = self.modules.get(keyword, None)
        if module:
            found = True
            if not module['instance'].__doc__:
                print 'Module %s does not have documentation' % keyword
            else:
                print module['instance'].__doc__
            return
        if not found:
            print 'Could not find module %s' % keyword
            
    def print_failed(self):
        """Parameter --failed"""
        print 'TODO: broken'
        
        # TODO: RE-IMPLEMENT
        
        """
        failed = self.shelve_session.setdefault('failed', [])
        if not failed:
            print 'No failed entries recorded'
        for entry in failed:
            tof = datetime(*entry['tof'])
            print '%16s - %s' % (tof.strftime('%Y-%m-%d %H:%M'), entry['title'])
            print '%16s - %s' % ('', entry['url'])
        """
        
    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        return
        
        # TODO: RE-IMPLEMENT
        
        """
        failed = self.shelve_session.setdefault('failed', [])
        f = {}
        f['title'] = entry['title']
        f['url'] = entry['url']
        f['tof'] = list(datetime.today().timetuple())[:-4]
        for lf in failed[:]:
            if lf['title'] == f['title'] and lf['url'] == f['url']:
                failed.remove(lf)
        failed.append(f)
        while len(failed) > 25:
            failed.pop(0)
        """
            
    def clear_failed(self):
        """Clears list of failed entries"""
        
        # TODO: RE-IMPLEMENT
        
        """
        print 'Cleared %i items.' % len(self.shelve_session.setdefault('failed', []))
        self.shelve_session['failed'] = []
        """

    def merge_dict_from_to(self, d1, d2):
        """Merges dictionary d1 into dictionary d2. d1 will remain in original form."""
        for k, v in d1.items():
            if k in d2:
                if type(v) == type(d2[k]):
                    if isinstance(v, dict):
                        self.merge_dict_from_to(d1[k], d2[k])
                    elif isinstance(v, list):
                        d2[k].extend(v)
                    elif isinstance(v, basestring) or isinstance(v, bool) or isinstance(v, int):
                        pass
                    else:
                        raise Exception('Unknown type: %s value: %s in dictionary' % (type(v), repr(v)))
                else:
                    raise MergeException('Merging key %s failed, conflicting datatypes.' % (k))
            else:
                d2[k] = v

    def execute(self):
        """Iterate trough all feeds and run them."""
        from feed import Feed

        if not self.config:
            log.critical('Configuration file is empty.')
            return

        # construct feed list
        feeds = self.config.get('feeds', {}).keys()
        if not feeds: 
            log.critical('There are no feeds in the configuration file!')
        # --only-feed
        if self.options.onlyfeed:
            ofeeds, feeds = feeds, []
            for name in ofeeds:
                if name.lower() == self.options.onlyfeed.lower(): 
                    feeds.append(name)
            if not feeds:
                log.critical('Could not find feed %s' % self.options.onlyfeed)

        terminate = {}
        for name in feeds:
            # validate (TODO: make use of validator?)
            if not isinstance(self.config['feeds'][name], dict):
                if isinstance(self.config['feeds'][name], str):
                    if name in self.modules:
                        log.error('\'%s\' is known keyword, but in wrong indentation level. \
                        Please indent it correctly under feed, it should have 2 more spaces \
                        than feed name.' % name)
                        continue
                log.error('\'%s\' is not a properly configured feed, please check indentation levels.' % name)
                continue
            # if feed name is prefixed with _ it's disabled
            if name.startswith('_'): 
                continue
            # create feed instance and execute it
            feed = Feed(self, name, self.config['feeds'][name])
            try:
                feed.session = Session()
                feed.execute()
                terminate[name] = feed
                feed.session.commit()
            except Exception, e:
                log.exception('Feed %s: %s' % (feed.name, e))
            finally:
                # note: will perform rollback if error occured (session has not been committed)
                feed.session.close()

        # execute terminate event for all feeds
        if not self.options.validate:
            for name, feed in terminate.iteritems():
                try:
                    feed.terminate()
                except Exception, e:
                    log.exception('Feed %s terminate: %s' % (name, e))            
