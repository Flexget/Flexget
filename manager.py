import os, os.path
import sys
import logging
import string
import types
import time
from datetime import tzinfo, timedelta, datetime
from feed import Feed
import shelve

try:
  from optparse import OptionParser, SUPPRESS_HELP
except ImportError:
  print 'Please install Optik 1.4.1 (or higher) or preferably update your Python'
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

class Manager:

    EVENTS = ['start', 'input', 'filter', 'resolve', 'download', 'modify', 'output', 'exit', 'terminate']
    
    def __init__(self):
        self.configname = None
        self.options = None
        self.modules = {}
        self.resolvers = {}
        self.session = {}
        self.config = {}
        self.initialized = False
        
        self.__instance = False

        # settings
        self.moduledir = os.path.join(sys.path[0], 'modules/')
        self.session_version = 2
        
        # logging formatting
        self.logging_detailed = '%(levelname)-8s %(name)-11s %(message)s'
        self.logging_normal = '%(levelname)-8s %(message)s'
        

        # Initialize logging for file, we must init it with some level now because
        # logging utility borks completely if any calls to logging is made before initialization
        # and load modules may call it before we know what level is used
        initial_level = logging.INFO
        try:
            logging.basicConfig(level=initial_level,
                                format='%(asctime)s '+self.logging_detailed,
                                filename=os.path.join(sys.path[0], 'flexget.log'),
                                filemode='a',
                                datefmt='%Y-%m-%d %H:%M:%S')
        except TypeError:
            # For pre-2.4 python
            logger = logging.getLogger() # root logger
            handler = logging.FileHandler(os.path.join(sys.path[0], 'flexget.log'))
            formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(initial_level)

        # initialize commandline options
        parser = OptionParser()
        parser.add_option('--test', action='store_true', dest='test', default=0,
                          help='Verbose what would happend on normal execution.')
        parser.add_option('--learn', action='store_true', dest='learn', default=0,
                          help='Matches are not downloaded but will be skipped in the future.')
        parser.add_option('--feed', action='store', dest='onlyfeed', default=None,
                          help='Run only specified feed from config.')
        parser.add_option('--no-cache', action='store_true', dest='nocache', default=0,
                          help='Disable caches. Works only in modules that have explicit support.')
        parser.add_option('--reset-session', action='store_true', dest='reset', default=0,
                          help='Forgets everything that has been downloaded and learns current matches.')
        parser.add_option('--doc', action='store', dest='doc',
                          help='Display module documentation (example: --doc patterns). See --list.')
        parser.add_option('--list', action='store_true', dest='list', default=0,
                          help='List all available modules.')
        parser.add_option('--failed', action='store_true', dest='failed', default=0,
                          help='List recently failed entries.')
        parser.add_option('--clear-failed', action='store_true', dest='clear_failed', default=0,
                          help='Clear recently failed list.')
        parser.add_option('-c', action='store', dest='config', default='config.yml',
                          help='Specify configuration file. Default is config.yml')
        parser.add_option('-q', action='store_true', dest='quiet', default=0,
                          help='Disables stdout and stderr output. Logging is done only to file.')
        parser.add_option('-d', action='store_true', dest='details', default=0,
                          help='Display detailed process information.')
        parser.add_option('--experimental', action='store_true', dest='experimental', default=0,
                          help='Use experimental features.')
        parser.add_option('--debug', action='store_true', dest='debug', default=0,
                          help=SUPPRESS_HELP)
        parser.add_option('--dump', action='store_true', dest='dump', default=0,
                          help=SUPPRESS_HELP)

        # add module path to sys.path so they can import properly ..
        sys.path.append(self.moduledir)

        # load modules, modules may add more commandline parameters!
        self.load_modules(parser, self.moduledir)
        
        self.options = parser.parse_args()[0]

        # perform commandline sanity check(s)
        if self.options.test and self.options.learn:
            print '--test and --learn are mutually exclusive'
            sys.exit(1)
        if self.options.reset:
            self.options.learn = True

        # now once options are parsed set logging level properly
        if self.options.debug:
            # set 'mainlogger' to debug aswell or no debug output, this is done because of
            # shitty python logging that fails to output debug on console if basicConf level
            # is less (propably because I don't know how to use that pice of ... )
            logging.getLogger().setLevel(logging.DEBUG)
        if not self.options.quiet:
            # log to console
            console = logging.StreamHandler()
            console.setLevel(logging.DEBUG)
            if self.options.debug:
                formatter = logging.Formatter(self.logging_detailed)
            else:
                formatter = logging.Formatter(self.logging_normal)
            console.setFormatter(formatter)
            logging.getLogger().addHandler(console)

    def initialize(self):
        """Loads configuration and session file, separated to own method because of unittests"""
        if self.initialized: return
        start_time = time.clock()
      
        # load config & session
        try:
            self.load_config()
        except Exception, e:
            logging.critical(e)
            sys.exit(1)
            
        self.load_session()
            
        # check if session version number is different
        if self.session.setdefault('version', self.session_version) != self.session_version:
            if not self.options.learn:
                logging.critical('Your session is broken or from older incompatible version of flexget. '\
                                 'Run application with --reset-session to resolve this. '\
                                 'Any new content downloaded between the previous successful execution and now will be lost. '\
                                 'You can (try to) spot new content from the report and download them manually.')
                sys.exit(1)
            self.session['version'] = self.session_version

        took = time.clock() - start_time
        logging.debug('Initialize took %.2f seconds' % took)
        self.initialized = True

    def load_config(self):
        """Load the configuration file"""
        possible = [os.path.join(sys.path[0], self.options.config), self.options.config]
        for config in possible:
            if os.path.exists(config):
                self.config = yaml.safe_load(file(config))
                self.configname = os.path.basename(config)[:-4]
                return
        logging.debug('Tried to read from: %s' % string.join(possible, ', '))
        raise Exception('Failed to load configuration file %s' % self.options.config)

    def load_session(self):
        if not self.configname:
            raise Exception('self.configname missing')

        if not self.options.reset:
            # load the old style file, if not found, migrate to new style
            if not self.load_session_yaml():
                self.load_session_shelf()
        else:
            self.load_session_yaml()
            self.load_session_shelf()

    def load_session_yaml(self):
        """Deprecated, is used only in migrating currently."""
        # TODO: remove at some point
        sessionfile = os.path.join(sys.path[0], 'session-%s.yml' % self.configname)
        if os.path.exists(sessionfile):
            # special case: reseting at the same time we would migrate -> just remove the old session file
            if self.options.reset:
                os.remove(sessionfile)
                return
            logging.info('Old sessionfile loaded. Session file will be migrated to the new format at the end of this run')
            try:
                self.session = yaml.safe_load(file(sessionfile))
                if type(self.session) != types.DictType:
                    raise Exception('Session file does not contain dictionary')
            except Exception, e:
                logging.critical('The session file has been broken. Execute flexget with --reset-session create new session and to avoid re-downloading everything. '\
                                 'Downloads between time of break and now are lost. You must download these manually. '\
                                 'This error is most likely caused by a bug in the software, check your log-file and report any tracebacks.')
                logging.exception('Reason: %s' % e)
                sys.exit(1)
            return True
        
        return False
                
    def load_session_shelf(self):
        sessiondb = os.path.join(sys.path[0], 'session-%s.db' % self.configname)
        # note: writeback must be True because how modules use our persistence.
        # See. http://docs.python.org/lib/node328.html
        if not self.options.reset:
            self.session = shelve.open(sessiondb, protocol=2, writeback=True)
        else:
            # create a new empty database
            self.session = shelve.open(sessiondb, flag='n', protocol=2, writeback=True)

    def sanitize(self, d):
        """Makes dictionary d contain only yaml.safe_dump compatible elements"""
        valid = [types.DictType, types.IntType, types.NoneType,
                 types.StringType, types.UnicodeType, types.BooleanType,
                 types.ListType, types.LongType, types.FloatType]
        for k in d.keys():
            if type(d[k])==types.ListType:
                for i in d[k][:]:
                    if not type(i) in valid:
                        logging.debug('Removed non yaml compatible list item from key %s %s' % (k, type([k])))
                        d[k].remove(i)
            if type(d[k])==types.DictType:
                self.sanitize(d[k])
            if not type(d[k]) in valid:
                logging.debug('Removed non yaml compatible key %s %s' % (k, type(d[k])))
                d.pop(k)

    def save_session(self):
        if not self.configname:
            raise Exception('self.configname missing')
            
        if self.options.dump:
            self.dump_session_yaml()

        self.save_session_shelf()

    def dump_session_yaml(self):
        """Dumps session into yaml file for easier debugging """
        try:
            fn = os.path.join(sys.path[0], 'dump-%s.yml' % self.configname)

            # mirgrate data
            dump = {}
            for k,v in self.session.iteritems():
                dump[k] = v

            f = file(fn, 'w')
            self.sanitize(dump)
            yaml.safe_dump(dump, f, allow_unicode=True)
            f.close()
            logging.info('Dumped session as YML to %s' % fn)
        except Exception, e:
            logging.exception("Failed to dump session data (%s)!" % e)

    def save_session_shelf(self):
        # not a shelve, we're most likely converting from an old style session
        if isinstance(self.session, dict):
            logging.info('Migrating from old-style session.')
            # create the new style session
            sessiondb = os.path.join(sys.path[0], 'session-%s.db' % self.configname)
            newsession = shelve.open(sessiondb, protocol=2)

            # mirgrate data
            for k,v in self.session.iteritems():
                newsession[k] = v

            # rename the old session file
            sessionfile = os.path.join(sys.path[0], 'session-%s.yml' % self.configname)
            os.rename(sessionfile, sessionfile+'-MIGRATED')

            newsession.close()

            logging.info('Migrating completed.')
            return
            
        self.session.close()
        
    def load_modules(self, parser, moduledir):
        """Load and call register on all modules"""
        # TODO: logging goes only to file due startup levels!
        loaded = {} # prevent modules being loaded multiple times when they're imported by other modules
        for module in self.find_modules(moduledir):
            ns = {}
            execfile(os.path.join(moduledir, module), ns, ns)
            for name in ns.keys():
                if loaded.get(name, False): continue
                if type(ns[name]) == types.ClassType:
                    if hasattr(ns[name], 'register'):
                        try:
                            instance = ns[name]()
                            # store current module instance so register method may access it
                            # without modules having to explicitly give it as parameter
                            self.__instance = instance
                        except:
                            logging.exception('Exception occured while creating instance %s' % name)
                            break
                        method = getattr(instance, 'register', None)
                        if callable(method):
                            try:
                                #logging.info('Loading module %s from %s' % (name, module))
                                method(self, parser)
                                loaded[name] = True
                            except RegisterException, e:
                                logging.critical('Error while registering module %s. %s' % (name, e.value))
                                break
                        else:
                            logging.error('Module %s register method is not callable' % name)


    def find_modules(self, directory):
        """Return array containing all modules in passed path"""
        modules = []
        prefixes = self.EVENTS + ['module', 'source']
        for m in os.listdir(directory):
            for p in prefixes:
                if m.startswith(p+'_') and m.endswith('.py'):
                    modules.append(m)
        return modules

    def get_settings(self, keyword, defaults={}):
        """
            Return defaults & settings for a keyword. You may optional defaults that will be used
            as default values where user has not specified anything.

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
        #print "keyword: %s defaults: %s config: %s" % (keyword, defaults, config)
        self.merge_dict(defaults, config)
        return config

    def register(self, **kwargs):
        """
            Modules call this method to register themselves.
            Mandatory arguments:
                keyword      - Configuration
                event        - Specifies event when module is executed in feed (and implies what it does)
                callback     - Method that is called when module is being executed
            Optional arguments:
                instance     - Instance of module (self)
                order        - When multiple modules are enabled this is used to
                               determine execution order. Default 16384.
                builtin      - Set to True if module should be executed always
                debug_module - Set to True to hide this module from --list etc
        """
        # validate passed arguments
        for arg in ['keyword', 'callback', 'event']:
            if not kwargs.has_key(arg):
                raise RegisterException('Parameter %s is missing from register arguments' % arg)
        if not callable(kwargs['callback']):
            raise RegisterException('Passed method not callable.')
        event = kwargs.get('event')
        if not event in self.EVENTS:
            raise RegisterException('Module has invalid event %s' % event)
        self.modules.setdefault(event, {})
        # check if there is already registered keyword with same event
        if self.modules[event].has_key(kwargs['keyword']):
            by = self.modules[event][kwargs['keyword']]['instance']
            raise RegisterException('Duplicate keyword with same event %s. Keyword: %s Reserved by: %s' % (event, kwargs['keyword'], by.__class__.__name__))
        # get module instance from load_modules if it's not given
        kwargs.setdefault('instance', self.__instance)
        # set optional parameter default values
        kwargs.setdefault('order', 16384)
        kwargs.setdefault('builtin', False)
        self.modules[event][kwargs['keyword']] = kwargs

    def register_resolver(self, **kwargs):
        """
            Resolver modules call this method to register themselves.
        """
        # validate passed arguments
        for arg in ['name']:
            if not kwargs.has_key(arg):
                raise RegisterException('Parameter %s is missing from register arguments' % arg)
        instance = kwargs.get('instance', self.__instance)
        name = kwargs['name']
        if not callable(getattr(instance, 'resolvable', None)):
            raise RegisterException('Resolver %s is missing resolvable method' % name)
        if not callable(getattr(instance, 'resolvable', None)):
            raise RegisterException('Resolver %s is missing resolve method' % name)
        if self.resolvers.has_key(name):
            raise RegisterException('Resolver %s is already registered' % name)
        self.resolvers[name] = instance

    def get_modules_by_event(self, event):
        """Return all modules by event."""
        result = []
        for keyword, module in self.modules.get(event, {}).items():
            if module['event'] == event:
                result.append(module)
        return result

    def print_module_list(self):
        print '-'*60
        print '%-20s%-30s%s' % ('Keyword', 'Roles', '--doc')
        print '-'*60
        modules = []
        roles = {}
        for event in self.EVENTS:
            ml = self.get_modules_by_event(event)
            for m in ml:
                dupe = False
                for module in modules:
                    if module['keyword'] == m['keyword']: dupe = True
                if not dupe:
                    modules.append(m)
            # build roles list
            for m in ml:
                if roles.has_key(m['keyword']):
                    roles[m['keyword']].append(event)
                else:
                    roles[m['keyword']] = [event]
        for module in modules:
            # do not include test classes, unless in debug mode
            if module.get('debug_module', False) and not self.options.debug:
                continue
            event = module['event']
            if modules.index(module) > 0: event = ''
            doc = 'Yes'
            if not module['instance'].__doc__: doc = 'No'
            print '%-20s%-30s%s' % (module['keyword'], string.join(roles[module['keyword']], ', '), doc)
        print '-'*60

    def print_module_doc(self):
        keyword = self.options.doc
        found = False
        for event in self.EVENTS:
            modules = self.modules.get(event, {})
            module = modules.get(keyword, None)
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
        self.initialize()
        failed = self.session.setdefault('failed', [])
        if not failed:
            print 'No failed entries recorded'
        for entry in failed:
            tof = datetime(*entry['tof'])
            print '%16s - %s' % (tof.strftime('%Y-%m-%d %H:%M'), entry['title'])
            print '%16s - %s' % ('', entry['url'])
        
    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        failed = self.session.setdefault('failed', [])
        f = {}
        f['title'] = entry['title']
        f['url'] = entry['url']
        f['tof'] = list(datetime.today().timetuple())[:-4]
        failed.append(f)
        while len(failed) > 25:
            failed.pop(0)
            
    def clear_failed(self):
        """Clears list of failed entries"""
        self.initialize()
        print 'Cleared %i items.' % len(self.session.setdefault('failed', []))
        self.session['failed'] = []

    def merge_dict(self, d1, d2):
        """Merges dictionary d1 into dictionary d2. d1 will remain in original form."""
        for k, v in d1.items():
            if d2.has_key(k):
                if type(v) == type(d2[k]):
                    if type(v) == types.DictType:
                        self.merge_dict(d1[k], d2[k])
                    elif type(v) == types.ListType:
                        d2[k].extend(v)
                    elif isinstance(v, basestring):
                        pass
                    else:
                        raise Exception('Unknown type %s in dictionary' % type(v))
                else:
                    raise Warning('Merging key %s failed, incompatible datatypes.' % (k))
            else:
                d2[k] = v

    def execute(self):
        """Iterate trough all feeds and run them."""
        self.initialize()
        try:
            if not self.config:
                logging.critical('Configuration file is empty.')
                return
            feeds = self.config.get('feeds', {}).keys()
            if not feeds: logging.critical('There are no feeds in the configuration file!')

            # --only-feed
            if self.options.onlyfeed:
                ofeeds, feeds = feeds, []
                for name in ofeeds:
                    if name.lower() == self.options.onlyfeed.lower(): feeds.append(name)
                if not feeds:
                    logging.critical('Could not find feed %s' % self.options.onlyfeed)

            feed_instances = {}
            for name in feeds:
                # if feed name is prefixed with _ it's disabled
                if name.startswith('_'): continue
                # create feed and execute it
                # merge global configuration into this feed config
                config = self.config['feeds'][name]
                try:
                    self.merge_dict(self.config.get('global', {}), config)
                except Exception, e:
                    logging.exception(e)
                    continue
                except Warning:
                    logging.critical('Global section has conflicting datatypes with feed %s configuration. Feed aborted.' % name)
                    continue
                feed = Feed(self, name, config)
                try:
                    feed.execute()
                    feed_instances[name] = feed
                except Exception, e:
                    logging.exception('Feed %s: %s' % (feed.name, e))

            # execute terminate event for all feeds
            for name, feed in feed_instances.iteritems():
                try:
                    feed.terminate()
                except Exception, e:
                    logging.exception('Feed %s terminate: %s' % (name, e))
                
        finally:
            if not self.options.test:
                self.save_session()
