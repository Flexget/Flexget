#!/usr/bin/env python

import urllib
import os, os.path
import re
import sys
import logging
import string
import types
from datetime import tzinfo, timedelta, datetime

import socket
socket.setdefaulttimeout(10) # time out in 10 seconds

try:
    from optparse import OptionParser, SUPPRESS_HELP
except ImportError:
    print "Please install Optik 1.4.1 (or higher) or preferably update your Python"
    sys.exit(1)

try:
    import yaml
except ImportError:
    print "Please install PyYAML from http://pyyaml.org/wiki/PyYAML or from your distro repository"
    sys.exit(1)

class RegisterException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class ResolverException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Manager:

    moduledir = os.path.join(sys.path[0], "modules/")

    EVENTS = ["start", "input", "filter", "resolve", "download", "modify", "output", "exit"]

    SESSION_VERSION = 2

    # logging formatting
    LOGGING_DETAILED = '%(levelname)-8s %(name)-11s %(message)s'
    LOGGING_NORMAL = '%(levelname)-8s %(message)s'
    
    def __init__(self):
        self.configname = None
        self.options = None
        self.modules = {}
        self.resolvers = {}
        self.session = {}
        self.config = {}

        # Initialize logging for file, we must init it with some level now because
        # logging utility borks completely if any calls to logging is made before initialization
        # and load modules may call it before we know what level is used
        initial_level = logging.INFO
        try:
            logging.basicConfig(level=initial_level,
                                format='%(asctime)s '+self.LOGGING_DETAILED,
                                filename=os.path.join(sys.path[0], 'flexget.log'),
                                filemode="a",
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
        parser.add_option("--test", action="store_true", dest="test", default=0,
                          help="Verbose what would happend on normal execution.")
        parser.add_option("--learn", action="store_true", dest="learn", default=0,
                          help="Matches are not downloaded but will be skipped in the future.")
        parser.add_option("--feed", action="store", dest="onlyfeed", default=None,
                          help="Run only specified feed from config.")
        parser.add_option("--no-cache", action="store_true", dest="nocache", default=0,
                          help="Disable caches. Works only in modules that have explicit support.")
        parser.add_option("--reset-session", action="store_true", dest="reset", default=0,
                          help="Forgets everything that has been downloaded and learns current matches.")
        parser.add_option("--doc", action="store", dest="doc",
                          help="Display module documentation (example: --doc patterns). See --list.")
        parser.add_option("--list", action="store_true", dest="list", default=0,
                          help="List all available modules.")
        parser.add_option("--failed", action="store_true", dest="failed", default=0,
                          help="List recently failed entries.")
        parser.add_option("--clear-failed", action="store_true", dest="clear_failed", default=0,
                          help="Clear recently failed list.")
        parser.add_option("-c", action="store", dest="config", default="config.yml",
                          help="Specify configuration file. Default is config.yml")
        parser.add_option("-q", action="store_true", dest="quiet", default=0,
                          help="Disables stdout and stderr output. Logging is done only to file.")
        parser.add_option("-d", action="store_true", dest="details", default=0,
                          help="Display detailed process information.")
        parser.add_option("--debug", action="store_true", dest="debug", default=0,
                          help=SUPPRESS_HELP)

        # add module path to sys.path so they can import properly ..
        sys.path.append(self.moduledir)

        # load modules, modules may add more commandline parameters!
        self.load_modules(parser)
        self.options = parser.parse_args()[0]

        # perform commandline sanity check(s)
        if self.options.test and self.options.learn:
            print "--test and --learn are mutually exclusive"
            sys.exit(1)

        # now once options are parsed set logging level properly
        level = logging.INFO
        if self.options.debug:
            level = logging.DEBUG
            # set 'mainlogger' to debug aswell or no debug output, this is done because of
            # shitty python logging that fails to output debug on console if basicConf level
            # is less (propably because I don't know how to use that pice of ... )
            logging.getLogger().setLevel(logging.DEBUG)
        if not self.options.quiet:
            self.__init_console_logging(level)

        # load config & session
        self.load_config()
        if self.options.reset:
            self.options.learn = True
        else:
            self.load_session()
        # check if session version number is different
        if self.session.setdefault('version', self.SESSION_VERSION) != self.SESSION_VERSION:
            if not self.options.learn:
                logging.critical('Your session is broken or from older incompatible version of flexget. '\
                                 'Run application with --reset-session to resolve this. '\
                                 'Any new content downloaded between the previous successful execution and now will be lost. '\
                                 'You can (try to) spot new content from the report and download them manually.')
                sys.exit(1)
            self.session['version'] = self.SESSION_VERSION

    def __init_console_logging(self, log_level):
        """Initialize logging for stdout"""
        # define a Handler which writes to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        # set a format which is simpler for console use
        if self.options.debug:
            formatter = logging.Formatter(self.LOGGING_DETAILED)
        else:
            formatter = logging.Formatter(self.LOGGING_NORMAL)
        # tell the handler to use this format
        console.setFormatter(formatter)
        # add the handler to the root logger
        logging.getLogger().addHandler(console)

    def load_config(self):
        """Load the configuration file"""
        possible = [os.path.join(sys.path[0], self.options.config), self.options.config]
        for config in possible:
            if os.path.exists(config):
                self.config = yaml.safe_load(file(config))
                self.configname = os.path.basename(config)[:-4]
                return
        logging.error("ERROR: No configuration file found!")
        sys.exit(0)

    def load_session(self):
        # sessions are config-specific
        if self.configname==None: raise Exception('self.configname missing')
        sessionfile = os.path.join(sys.path[0], 'session-%s.yml' % self.configname)
        if os.path.exists(sessionfile):
            try:
                self.session = yaml.safe_load(file(sessionfile))
                if type(self.session) != types.DictType:
                    raise Exception('Session file does not contain dictionary')
            except Exception, e:
                logging.critical("The session file has been broken. Execute flexget with --reset-session create new session and to avoid re-downloading everything. "\
                "Downloads between time of break and now are lost. You must download these manually. "\
                "This error is most likely caused by a bug in the software, check your log-file and report any tracebacks.")
                logging.exception('Reason: %s' % e)
                sys.exit(1)

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
        try:
            if self.configname==None: raise Exception('self.configname missing')
            sessionfile = os.path.join(sys.path[0], 'session-%s.yml' % self.configname)
            f = file(sessionfile, 'w')
            self.sanitize(self.session)
            yaml.safe_dump(self.session, f) # safe_dump removes !!python/unicode which fails to load
            f.close()
        except Exception, e:
            logging.exception("Failed to save session data (%s)!" % e)
            logging.critical(yaml.dump(self.session))
        
    def load_modules(self, parser):
        """Load and call register on all modules"""
        loaded = {} # prevent modules being loaded multiple times when they're imported by other modules
        for module in self.find_modules(self.moduledir):
            ns = {}
            execfile(os.path.join(self.moduledir, module), ns, ns)
            for name in ns.keys():
                if loaded.get(name, False): continue
                if type(ns[name]) == types.ClassType:
                    if hasattr(ns[name], 'register'):
                        try:
                            instance = ns[name]()
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
                                logging.error('Error while registering module %s. %s' % (name, e.value))
                                break
                        else:
                            logging.error('Module %s register method is not callable' % name)


    def find_modules(self, directory):
        """Return array containing all modules in passed path"""
        modules = []
        prefixes = self.EVENTS + ['module', 'source']
        for m in os.listdir(directory):
            for p in prefixes:
                if m.startswith(p+'_') and m.endswith(".py"):
                    modules.append(m)
        return modules

    def get_cache(self):
        """Returns cache for modules"""
        # TODO: after plenty of refactoring only this remains, remove completely?
        return self.session.setdefault('cache', {})

    def register(self, **kwargs):
        """
            Modules call this method to register themselves.
            Mandatory arguments:
                instance    - instance of module (self)
                keyword     - maps directly into config
                callback    - method that is called when module is executed
                event       - specifies when module is executed and implies what it does
            Optional arguments:
                order       - when multiple modules are enabled this is used to
                              determine execution order. Default 16384.
                builtin     - set to True if module should be executed always
        """
        # validate passed arguments
        for arg in ['instance', 'keyword', 'callback', 'event']:
            if not kwargs.has_key(arg):
                raise RegisterException('Parameter %s is missing from register arguments' % arg)
        if not callable(kwargs['callback']):
            raise RegisterException("Passed method not callable.")
        event = kwargs.get('event')
        if not event in self.EVENTS:
            raise RegisterException("Module has invalid event '%s'. Recognized events are: %s." % (event, string.join(self.EVENTS, ', ')))
        self.modules.setdefault(event, {})
        if self.modules[event].has_key(kwargs['keyword']):
            by = self.modules[event][kwargs['keyword']]['instance']
            raise RegisterException("Duplicate keyword with same event '%s'. Keyword: '%s' Reserved by: '%s'" % (event, kwargs['keyword'], by.__class__.__name__))
        # set optional parameter default values
        kwargs.setdefault('order', 16384)
        kwargs.setdefault('builtin', False)
        self.modules[event][kwargs['keyword']] = kwargs

    def register_resolver(self, **kwargs):
        """
            Resolver modules call this method to register themselves.
        """
        # validate passed arguments
        for arg in ['instance', 'name']:
            if not kwargs.has_key(arg):
                raise RegisterException('Parameter %s is missing from register arguments' % arg)
        instance = kwargs['instance']
        name = kwargs['name']
        if not callable(getattr(instance, 'resolvable', None)):
            raise RegisterException('Resolver %s is missing resolvable method' % name)
        if not callable(getattr(instance, 'resolvable', None)):
            raise RegisterException('Resolver %s is missing resolve method' % name)
        if self.resolvers.has_key(name):
            raise RegisterException('Resolver %s is already registered' % name)
        self.resolvers[name] = kwargs['instance']

    def get_modules_by_event(self, event):
        """Return all modules by event."""
        result = []
        for keyword, module in self.modules.get(event, {}).items():
            if module['event'] == event:
                result.append(module)
        return result

    def print_module_list(self):
        print "-"*60
        print "%-20s%-30s%s" % ('Keyword', 'Roles', '--doc')
        print "-"*60
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
            if modules.index(module) > 0: event = ""
            doc = "Yes"
            if module['instance'].__doc__ == None: doc = "No"
            print "%-20s%-30s%s" % (module['keyword'], string.join(roles[module['keyword']], ', '), doc)
        print "-"*60

    def print_module_doc(self):
        keyword = self.options.doc
        found = False
        for event in self.EVENTS:
            modules = self.modules.get(event, {})
            module = modules.get(keyword, None)
            if module:
                found = True
                if module['instance'].__doc__ == None:
                    print "Module %s does not have documentation" % keyword
                else:
                    print module['instance'].__doc__
                return
        if not found:
            print "Could not find module %s" % keyword
            
    def print_failed(self):
        failed = self.session.setdefault('failed', [])
        if not failed:
            print "No failed entries recorded"
        for entry in failed:
            tof = datetime(*entry['tof'])
            print "%16s - %s" % (tof.strftime('%Y-%m-%d %H:%M'), entry['title'])
            print "%16s - %s" % ('', entry['url'])
        
    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        failed = self.session.setdefault('failed', [])
        f = {}
        f['title'] = entry['title']
        f['url'] = entry['url']
        f['tof'] = list(datetime.today().timetuple())[:-4]
        failed.append(f)
        while len(failed) > 255:
            failed.pop(0)
            
    def clear_failed(self):
        """Clears list of failed entries"""
        print "Cleared %i items." % len(self.session.setdefault('failed', []))
        self.session['failed'] = []

    def execute(self):
        """Iterate trough all feeds and run them."""
        try:
            feeds = self.config.get('feeds', {}).keys()
            if not feeds: logging.critical('There are no feeds in the configuration file!')

            # --only-feed
            if self.options.onlyfeed:
                ofeeds, feeds = feeds, []
                for name in ofeeds:
                    if name.lower() == self.options.onlyfeed.lower(): feeds.append(name)
                if not feeds:
                    logging.critical('Could not find feed %s' % self.options.onlyfeed)
                
            for name in feeds:
                # if feed name is prefixed with _ it's disabled
                if name.startswith('_'): continue
                # create feed and execute it
                feed = Feed(self, name, self.config['feeds'][name])
                try:
                    feed.execute()
                except Exception, e:
                    logging.exception("Feed %s: %s" % (feed.name, e))
        finally:
            if not self.options.test:
                self.save_session()

class ModuleCache:

    """
        Provides dictionary-like persistent storage for modules, allows saving key value pair for n number of days. Purges old
        entries to keep storage size in reasonable sizes.
    """

    log = logging.getLogger('modulecache')

    def __init__(self, name, storage):
        self.__storage = storage.setdefault(name, {})

    def set_namespace(self, name):
        self._cache = self.__storage.setdefault(name, {})
        self.__namespace = name
        self.__purge()

    def get_namespace(self):
        return self.__namespace

    def get_namespaces(self):
        """Return array of known namespaces in this cache"""
        return self.__storage.keys()
    
    def store(self, key, value, days=45):
        """Stores key value pair for number of days. Non yaml compatible values are not saved."""
        item = {}
        item['stored'] = datetime.today().strftime('%Y-%m-%d')
        item['days'] = days
        item['value'] = value
        self._cache[key] = item

    def storedetault(self, key, value, days=45):
        """Identical to dictionary setdefault"""
        undefined = object()
        item = self.get(key, undefined)
        if item is undefined:
            self.log.debug('storing default for %s, value %s' % (key, value))
            self.store(key, value, days)
            return self.get(key)
        else:
            return item

    def get(self, key, default=None):
        """Return value by key from cache. Return None or default if not found"""
        item = self._cache.get(key)
        if item == None:
            return default
        else:
            return item['value']

    def __purge(self):
        """Remove all values from cache that have passed their expiry date"""
        now = datetime.today()
        for key in self._cache.keys():
            item = self._cache[key]
            y,m,d = item['stored'].split('-')
            stored = datetime(int(y), int(m), int(d))
            delta = now - stored
            if delta.days > item['days']:
                self.log.debug('Purging from cache %s' % (str(item)))
                self._cache.pop(key)

class Feed:

    def __init__(self, manager, name, config):
        """
            name - name of the feed
            config - yaml configuration (dict)
        """
        self.name = name
        self.config = config
        self.manager = manager

        # merge global configuration into this feed config
        self.__merge_config(manager.config.get('global', {}), config)

        self.cache = ModuleCache(name, manager.get_cache())
        self.shared_cache = ModuleCache('_shared_', manager.get_cache())

        self.entries = []
        # accepted entries are always accepted, filtering does not affect them
        self.__accepted = [] 
        self.__filtered = []
        # rejected enteries are removed unconditionally, even if accepted
        self.__rejected = []
        self.__failed = []
        self.__abort = False
        self.__purged = 0
        
        # loggers
        #self.details = logging.getLogger('details')
        #self.details.disabled = 1
        
    def __merge_config(self, d1, d2):
        """Merges dictionary d1 into dictionary d2"""
        for k, v in d1.items():
            if d2.has_key(k):
                if type(v) == type(d2[k]):
                    if type(v)==types.DictType: self.__merge_config(self, d1[k], d2[k])
                    elif type(v)==types.ListType: d2[k].extend(v)
                    else: raise Exception('BUG: Unknown type %s in config' % type(v))
                else: raise Exception('Global keyword %s is incompatible with feed %s. Keywords are not same datatype.' % (k, self.name))
            else: d2[k] = v

    def _purge(self):
        """Purge filtered entries from feed. Call this from module only if you know what you're doing."""
        for entry in self.entries[:]:
            if entry in self.__filtered and not entry in self.__accepted:
                logging.debug('Purging entry %s' % entry)
                self.entries.remove(entry)
                self.__purged += 1
        self.__filtered = []
        
    def __purge_failed(self):
        """Purge failed entries from feed."""
        for entry in self.entries[:]:
            if entry in self.__failed:
                logging.debug('Purging failed entry %s' % entry)
                self.entries.remove(entry)

    def __filter_rejected(self):
        if not self.__rejected:
            return
        for entry in self.entries[:]:
            if entry in self.__rejected:
                logging.debug('Purging immediately entry %s' % entry)
                self.entries.remove(entry)
                self.__purged += 1
        self.__rejected = []

    def accept(self, entry):
        """Accepts this entry."""
        if not entry in self.__accepted:
            self.__accepted.append(entry)
            self.verbose_details('Accepted %s' % entry['title'])

    def filter(self, entry):
        """Mark entry to be filtered uless told otherwise. Entry may still be accepted."""
        # accepted checked only because it makes more sense when verbosing details
        if not entry in self.__filtered and not entry in self.__accepted:
            self.__filtered.append(entry)
            self.verbose_details('Filtered %s' % entry['title'])

    def reject(self, entry):
        """Reject this entry immediattely and permanently."""
        # schedule immediately filtering after this module has done execution
        if not entry in self.__rejected:
            self.__rejected.append(entry)
            self.verbose_details('Rejected %s' % entry['title'])

    def failed(self, entry):
        """Mark entry failed"""
        logging.debug("Marking entry '%s' as failed" % entry['title'])
        if not entry in self.__failed:
            self.__failed.append(entry)
            self.manager.add_failed(entry)
            self.verbose_details('Failed %s' % entry['title'])

    def get_failed_entries(self):
        """Return set containing failed entries"""
        return set(self.__failed)

    def get_succeeded_entries(self):
        """Return set containing successfull entries"""
        succeeded = []
        for entry in self.entries:
            if not entry in self.__failed:
                succeeded.append(entry)
        return succeeded

    def abort(self):
        """Abort this feed execution, no more modules will be executed."""
        self.__abort = True
        self.verbose_details('Aborting feed')

    def get_input_url(self, keyword):
        """
            Helper method for modules. Return url for a specified keyword.
            Supports configuration in following forms:
                <keyword>: <address>
            and
                <keyword>:
                    url: <address>
        """
        if type(self.config[keyword])==types.DictType:
            if not self.config[keyword].has_key('url'):
                raise Exception('Input %s has invalid configuration, url is missing.' % keyword)
            return self.config[keyword]['url']
        else:
            return self.config[keyword]

    def __get_order(self, module):
        """Return order for module in this feed. Uses default value if no value is configured."""
        order = module['order']
        keyword = module['keyword']
        if self.config.has_key(keyword):
            if type(self.config[keyword])==types.DictType:
                order = self.config[keyword].get('order', order)
        return order

    def __sort_modules(self, a, b):
        a = self.__get_order(a)
        b = self.__get_order(b)
        return cmp(a, b)

    def __run_modules(self, event):
        """Execute module callbacks by event type if module is configured for this feed."""
        modules = manager.get_modules_by_event(event)
        # Sort modules based on module order.
        # Order can be also configured in which case given value overwrites module default.
        modules.sort(self.__sort_modules)
        for module in modules:
            keyword = module['keyword']
            if self.config.has_key(keyword) or (module['builtin'] and not self.config.get('disable_builtins', False)):
                try:
                    # set cache namespaces to this module realm
                    self.cache.set_namespace(keyword)
                    self.shared_cache.set_namespace(keyword)
                    # store execute info
                    self.__current_event = event
                    self.__current_module = keyword
                    # call module
                    module['callback'](self)
                    # check for priority operations
                    self.__filter_rejected()
                    if self.__abort: return
                except Warning, w:
                    logging.warning(w)
                except Exception, e:
                    logging.exception('Module %s: %s' % (keyword, e))

    def log_once(self, s, log=logging):
        """Log string s once"""
        import md5
        m = md5.new()
        m.update(s)
        sum = m.hexdigest()
        seen = self.shared_cache.get('log-%s' % sum, False)
        if (seen):
            return
        self.shared_cache.store('log-%s' % sum, True, 30)
        log.info(s)


    def verbose_progress(self, s):
        """Verboses progress, outputs only in non quiet mode."""
        # TODO: implement trough own logger?
        if not manager.options.quiet:
          logging.info(s)
          
    def verbose_details(self, s):
        # TODO: implement trough own logger?
        if manager.options.details:
            print "+ %-8s %-12s %s" % (self.__current_event, self.__current_module, s)

    def verbose_details_entries(self):
        if manager.options.details:
            for entry in self.entries:
                self.verbose_details('%s' % entry['title'])

    def resolvable(self, entry):
        """Return true if entry is resolvable by registered resolver"""
        for name, resolver in manager.resolvers.iteritems():
            if resolver.resolvable(self, entry):
                return True
        return False
        
    def resolve(self, entry):
        """Resolves given entry url. Raises ResolverException if resolve failed."""
        tries = 0
        while self.resolvable(entry):
            tries += 1
            if (tries>1000):
                raise ResolverException('resolve was left in infinite loop, aborting! url=%s' % entry['url'])
            for name, resolver in manager.resolvers.iteritems():
                if resolver.resolvable(self, entry):
                    logging.debug('%s resolving %s' % (name, entry['url']))
                    if not resolver.resolve(self, entry):
                        raise ResolverException('Resolver %s failed to resolve %s' % (name, entry['title']))
    

    def _resolve_entries(self):
        """Resolves all entries in feed"""
        for entry in self.entries:
            try:
                self.resolve(entry)
            except ResolverException, r:
                logging.warning(r)
                self.failed(entry)
            except Exception, e:
                logging.exception(e)
    
    def execute(self):
        """Execute this feed, runs all events in order of events array."""
        for event in self.manager.EVENTS:
            # when learning, skip few events
            if self.manager.options.learn:
                if event in ['download', 'output']: continue
            # handle resolve event a bit special
            if event == 'resolve':
                self._resolve_entries()
                self.__purge_failed()
                continue
            # run all modules with specified event
            self.__run_modules(event)
            # purge filtered and failed entries
            self._purge()
            self.__purge_failed()
            # verbose some progress
            if event == 'input':
                self.verbose_details_entries()
                self.verbose_progress('Feed %s produced %s entries.' % (self.name, len(self.entries)))
            if event == 'filter':
                self.verbose_progress('Feed %s filtered %s entries (%s remains).' % (self.name, self.__purged, len(self.entries)))
            # if abort flag has been set feed should be aborted now
            if self.__abort:
                logging.info('Aborting feed %s' % self.name)
                return

if __name__ == "__main__":
    manager = Manager()
    if manager.options.doc:
        manager.print_module_doc()
    elif manager.options.list:
        manager.print_module_list()
    elif manager.options.failed:
        manager.print_failed()
    elif manager.options.clear_failed:
        manager.clear_failed()
    else:
        manager.execute()
