#!/usr/bin/env python

# pybtrss - Downloads bittorrent files from RSS feeds
#
# Copyright (C) 2006 Riku 'Shrike' Lindblad
# Copyright (C) 2007 Marko Koivusalo
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

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

class Manager:

    moduledir = os.path.join(sys.path[0], "modules/")
    module_types = ["start", "input", "filter", "download", "modify", "output", "exit"]

    SESSION_VERSION = 2

    # logging formatting
    LOGGING_DETAILED = '%(levelname)-8s %(name)-11s %(message)s'
    LOGGING_NORMAL = '%(levelname)-8s %(message)s'
    
    def __init__(self):
        self.configname = None
        self.options = None
        self.modules = {}
        self.session = {}
        self.config = {}

        # Initialize logging for file, we must init it with some level now because
        # logging utility borks completely if any calls to logging is made before initialization
        # and load modules may call it before we know what level is used
        initial_level = logging.INFO
        try:
            logging.basicConfig(level=initial_level,
                                format=self.LOGGING_DETAILED,
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
        parser.add_option("-c", action="store", dest="config", default="config.yml",
                          help="Specify configuration file. Default is config.yml")
        parser.add_option("-q", action="store_true", dest="quiet", default=0,
                          help="Disables stdout and stderr output. Logging is done only to file.")
        parser.add_option("-d", action="store_true", dest="debug", default=0,
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
        # if new session, init version
        if len(self.session) == 0:
            self.session['version'] = self.SESSION_VERSION
        # check if session version number is different
        if self.session.get('version', 0) != self.SESSION_VERSION:
            if not self.options.learn:
                logging.critical('Your session is broken or from older incompatible version of flexget. '\
                                 'Run application with --reset-session to resolve this. '\
                                 'Unfornattely new content between previous successfull execution and now are lost. '\
                                 'You can (try to) spot new content from report and download them manually.')
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
                    raise Exception('Sessionfile does not contain dictionary')
            except Exception, e:
                logging.critical("Sessionfile has been broken. Execute flexget with --reset-session create new session and to avoid re-downloading everything. "\
                "Downloads between time of break and now are lost. You must download these manually. "\
                "This error is most likelly because of bug in software, check your log-file and report any tracebacks." % sessionfile)
                logging.exception('Load failure: %s' % e)
                sys.exit(1)

    def save_session(self):
        try:
            if self.configname==None: raise Exception('self.configname missing')
            sessionfile = os.path.join(sys.path[0], 'session-%s.yml' % self.configname)
            f = file(sessionfile, 'w')
            yaml.safe_dump(self.session, f) # safe_dump removes !!python/unicode which fails to load
            f.close()
        except Exception, e:
            logging.exception("Failed to save session data (%s)!" % e)
            logging.critical(yaml.dump(self.session))
        
    def load_modules(self, parser):
        """Load and call register on all modules"""
        for module in self.find_modules(self.moduledir):
            ns = {}
            execfile(os.path.join(self.moduledir, module), ns, ns)
            for name in ns.keys():
                if type(ns[name]) == types.ClassType:
                    if hasattr(ns[name], 'register'):
                        try:
                            instance = ns[name]()
                        except:
                            logging.exception('Exception occured while creating instance %s' % name)
                            break
                        method = getattr(instance, 'register', None)
                        if callable(method):
                            logging.debug('Module %s loaded' % name)
                            try:
                                method(self, parser)
                            except RegisterException, e:
                                logging.exception('Error while registering %s. %s' % (name, e.value))
                                break
                        else:
                            logging.error('Module %s register method is not callable' % name)


    def find_modules(self, directory):
        """Return array containing all modules in passed path"""
        modules = []
        prefixes = self.module_types + ['module', 'source']
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
                type        - specifies when module is executed and implies what it does
            Optional arguments:
                order       - when multiple modules are enabled this is used to
                              determine execution order. Default 16384.
                builtin     - set to True if module should be executed always
        """
        # validate passed arguments
        for arg in ['instance', 'keyword', 'callback', 'type']:
            if not kwargs.has_key(arg):
                raise RegisterException('Parameter %s is missing from register arguments' % arg)
        module_type = kwargs['type']
        if not callable(kwargs['callback']):
            raise RegisterException("Passed method not callable.")
        if not module_type in self.module_types:
            raise RegisterException("Module has invalid type '%s'. Recognized types are: %s." % (kwargs['type'], string.join(self.module_types, ', ')))
        self.modules.setdefault(module_type, {})
        if self.modules[module_type].has_key(kwargs['keyword']):
            raise RegisterException("Duplicate keyword with same type: '%s'." % (kwargs['keyword']))
        # set optional parameter default values
        kwargs.setdefault('order', 16384)
        kwargs.setdefault('builtin', False)
        self.modules[module_type][kwargs['keyword']] = kwargs
        logging.debug("Module registered type: %s keyword: %s order: %d" % (kwargs['type'], kwargs['keyword'], kwargs['order']))

    def get_modules_by_type(self, module_type):
        """Return all modules by type."""
        result = []
        for keyword, module in self.modules.get(module_type, {}).items():
            if module['type'] == module_type:
                result.append(module)
        return result

    def print_module_list(self):
        print "-"*60
        print "%-20s%-30s%s" % ('Keyword', 'Roles', '--doc')
        print "-"*60
        modules = []
        roles = {}
        for module_type in self.module_types:
            ml = self.get_modules_by_type(module_type)
            for m in ml:
                dupe = False
                for module in modules:
                    if module['keyword'] == m['keyword']: dupe = True
                if not dupe:
                    modules.append(m)
            # build roles list
            for m in ml:
                if roles.has_key(m['keyword']):
                    roles[m['keyword']].append(module_type)
                else:
                    roles[m['keyword']] = [module_type]
        for module in modules:
            # do not include test classes, unless in debug mode
            if module.get('debug_module', False) and not self.options.debug:
                continue
            module_type = module['type']
            if modules.index(module) > 0: module_type=""
            doc = "Yes"
            if module['instance'].__doc__ == None: doc = "No"
            print "%-20s%-30s%s" % (module['keyword'], string.join(roles[module['keyword']], ', '), doc)
        print "-"*60

    def print_module_doc(self):
        keyword = self.options.doc
        found = False
        for module_type in self.module_types:
            modules = self.modules.get(module_type, {})
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
        if len(failed) == 0: print "No failed entries recorded"
        for entry in failed:
            tof = datetime(*entry['tof'])
            print "%-12s TITLE: %-30s URL: %s" % (tof.strftime('%Y-%m-%d %H:%M'), entry['title'], entry['url'])
        
    def add_failed(self, entry):
        """Adds entry to internal failed list, displayed with --failed"""
        failed = self.session.setdefault('failed', [])
        entry['tof'] = list(datetime.today().timetuple())[:-4]
        failed.append(entry)
        while len(failed) > 255:
            failed.pop(0)

    def execute(self):
        """Iterate trough all feeds and run them."""
        try:
            feeds = self.config.get('feeds', {})
            feeds = feeds.keys() # array of feed names
            if len(feeds)==0: logging.critical('There are no feeds in configuration file!')

            # --only-feed
            if self.options.onlyfeed:
                ofeeds, feeds = feeds, []
                for name in ofeeds:
                    if name.lower() == self.options.onlyfeed.lower(): feeds.append(name)
                if len(feeds)==0:
                    logging.critical('Could not find feed %s' % self.options.onlyfeed)
                
            for name in feeds:
                # if feed name is prefixed with _ it's disabled
                if name.startswith('_'): continue
                last = len(feeds) - 1 == feeds.index(name)
                # create feed and execute it
                feed = Feed(self, name, self.config['feeds'][name], last)
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
        self.__cache = self.__storage.setdefault(name, {})
        self.__namespace = name
        self.__purge()

    def get_namespace(self):
        return self.__namespace

    def get_namespaces(self):
        """Return array of known namespaces in this cache"""
        return self.__storage.keys()
    
    def store(self, key, value, days=60):
        """Stores key value pair for number of days. Value must be yaml compatible."""
        item = {}
        item['stored'] = datetime.today().strftime('%Y-%m-%d')
        item['days'] = days
        item['value'] = value
        self.__cache[key] = item

    def storedetault(self, key, value, days=60):
        """Identical to dictionary setdefault"""
        item = self.get(key)
        if item == None:
            self.log.debug('storing default for %s, value %s' % (key, value))
            self.store(key, value, days)
            return value
        else:
            return item

    def get(self, key, default=None):
        """Return value by key from cache. Return None or default if not found"""
        item = self.__cache.get(key)
        if item == None:
            return default
        else:
            return item['value']

    def __purge(self):
        """Remove all values from cache that have passed their expiry date"""
        now = datetime.today()
        for key in self.__cache.keys():
            item = self.__cache[key]
            y,m,d = item['stored'].split('-')
            stored = datetime(int(y), int(m), int(d))
            delta = now - stored
            if delta.days > item['days']:
                self.log.debug('Purging from cache %s' % (str(item)))
                self.__cache.pop(key)

class Feed:

    def __init__(self, manager, name, config, last):
        """
            name - name of the feed
            config - yaml configuration (dict)
            last - boolean flag, true if this is last feed we are going to run
        """
        self.name = name
        self.config = config
        self.manager = manager
        self.last = last

        # merge global configuration into this feed config
        self.__merge_config(manager.config.get('global', {}), config)

        self.cache = ModuleCache(name, manager.get_cache())
        self.shared_cache = ModuleCache('_shared_', manager.get_cache())

        self.entries = []
        self.__accepted = [] # these entries are always accepted, filtering does not affect them
        self.__filtered = []
        self.__immediattely = []
        self.__failed = []
        self.__abort = False
        self.__purged = 0
        
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

    def __purge(self):
        """Purge filtered entries from feed"""
        for entry in self.entries[:]:
            if entry in self.__filtered and not entry in self.__accepted:
                logging.debug('Purging entry %s' % entry)
                self.entries.remove(entry)
                self.__purged += 1
        self.__filtered = []

    def __filter_immediately(self):
        if len(self.__immediattely) == 0: return
        for entry in self.entries[:]:
            if entry in self.__immediattely:
                logging.debug('Purging immediately entry %s' % entry)
                self.entries.remove(entry)
                self.__purged += 1
        self.__immediattely = []

    def accept(self, entry):
        """Accepts this entry"""
        if not entry in self.__accepted:
            self.__accepted.append(entry)

    def filter(self, entry, immediately=False):
        if immediately:
            # schedule immediately filtering after this module has done execution
            if not entry in self.__immediattely:
                self.__immediattely.append(entry)
        elif not entry in self.__filtered:
            self.__filtered.append(entry)

    def failed(self, entry):
        """Mark entry failed"""
        logging.debug("Marking entry '%s' as failed" % entry['title'])
        self.__failed.append(entry)
        self.manager.add_failed(entry)

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

    def __run_modules(self, module_type):
        modules = manager.get_modules_by_type(module_type)
        # Sort modules based on module order.
        # Order can be also configured in which case given value overwrites module default.
        modules.sort(self.__sort_modules)
        for module in modules:
            keyword = module['keyword']
            if self.config.has_key(keyword) or (module['builtin'] and not self.config.get('disable_builtins', False)):
                try:
                    # set cache namespaces
                    self.cache.set_namespace(keyword)
                    self.shared_cache.set_namespace(keyword)
                    # call module
                    logging.debug('executing %s %s' % (module_type, keyword))
                    module['callback'](self)
                    # check for priority operations
                    self.__filter_immediately()
                    if self.__abort: return
                except Warning, w:
                    logging.warning(w)
                except Exception, e:
                    logging.exception('Module %s: %s' % (keyword, e))

    def execute(self):
        """Execute this feed, runs all associated modules in order by type"""
        for module_type in self.manager.module_types:
            # when learning, skip few types
            if self.manager.options.learn:
                if module_type in ['download', 'output']: continue
            # run all modules with specified type
            self.__run_modules(module_type)
            # purge filtered entries
            self.__purge()
            # verbose some progress, unless in quiet mode (logging only) TODO: implement more widely trough custom level?
            if not manager.options.quiet:
                if module_type == 'input':
                    logging.info('Feed %s produced %s entries.' % (self.name, len(self.entries)))
                if module_type == 'filter':
                    logging.info('Feed %s filtered %s entries (%s remains).' % (self.name, self.__purged, len(self.entries)))
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
    else:
        manager.execute()
