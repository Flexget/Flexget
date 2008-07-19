import logging
import types
from datetime import datetime

class ResolverException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Entry(dict):

    """
        Represents one item in feed. Must have url and title fields.
        See. http://flexget.com/wiki/DevelopersEntry

        Internally stored original_url is neccessary because
        resolvers change this into something else and otherwise
        that information would be lost.
    """

    def __init__(self, *args):
        if len(args) == 2:
            self['title'] = args[0]
            self['url'] = args[1]

    def __setitem__(self, key, value):
        if key == 'url':
            if not self.has_key('original_url'):
                self['original_url'] = value
        dict.__setitem__(self, key, value)
    
    def safe_str(self):
        return "%s | %s" % (self['title'], self['url'])

    def isvalid(self):
        """Return True if entry is valid. Return False if this cannot be used."""
        if not self.has_key('title'):
            return False
        if not self.has_key('url'):
            return True
        return True

class ModuleCache:

    """
        Provides dictionary-like persistent storage for modules, allows saving key value pair
        for n number of days. Purges old entries to keep storage size in reasonable sizes.
    """

    log = logging.getLogger('modulecache')

    def __init__(self, name, storage):
        self.__storage = storage.setdefault(name, {})
        self._cache = None
        self.__namespace = None

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

    def storedefault(self, key, value, days=45):
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
        if item is None:
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
            Represents one feed in configuration.

            name - name of the feed
            config - yaml configuration (dict)
        """
        self.name = name
        self.config = config
        self.manager = manager

        self.cache = ModuleCache(name, manager.session.setdefault('cache', {}))
        self.shared_cache = ModuleCache('_shared_', manager.session.setdefault('cache', {}))

        self.entries = []
        
        # true when executing from unittest
        self.unittest = False
        
        # You should NOT change these arrays at any point, and in most cases not even read them!
        # Mainly public since unittest needs these
        
        self.accepted = [] # accepted entries are always accepted, filtering does not affect them
        self.filtered = [] # filtered entries
        self.rejected = [] # rejected entries are removed unconditionally, even if accepted
        self.failed = []
        
        self.__abort = False
        self.__purged = 0
        
        # state
        self.__current_event = None
        self.__current_module = None

        self.check_config()
        
    def _purge(self):
        """Purge filtered entries from feed. Call this from module only if you know what you're doing."""
        self.__purge(self.filtered, self.accepted)

    def __purge_failed(self):
        """Purge failed entries from feed."""
        self.__purge(self.failed, [], False)

    def __purge_rejected(self):
        """Purge rejected entries from feed."""
        self.__purge(self.rejected)

    def __purge(self, list, not_in_list=[], count=True):
        """Purge entries in list from feed.entries"""
        for entry in self.entries[:]:
            if entry in list and entry not in not_in_list:
                logging.debug('Purging entry %s' % entry.safe_str())
                self.entries.remove(entry)
                if count:
                    self.__purged += 1
        
    def __convert_entries(self):
        """Temporary method for converting dict entries into Entries"""
        count = 0
        for entry in self.entries[:]:
            if not isinstance(entry, Entry):
                e = Entry()
                for k,v in entry.iteritems():
                    e[k] = v
                self.entries.remove(entry)
                count += 1
                self.entries.append(e)
        if count>0:
            logging.warning('Feed %s converted %i old entries into new format. Some modules need upgrading (Event: %s Module: %s).' % (self.name, count, self.__current_event, self.__current_module))

    def accept(self, entry):
        """Accepts this entry."""
        if not entry in self.accepted:
            self.accepted.append(entry)
            if entry in self.filtered:
                self.filtered.remove(entry)
                self.verbose_details('Accepted previously filtered %s' % entry['title'])
            else:
                self.verbose_details('Accepted %s' % entry['title'])
                

    def filter(self, entry):
        """Mark entry to be filtered unless told otherwise. Entry may still be accepted."""
        # accepted checked only because it makes more sense when verbosing details
        if not entry in self.filtered and not entry in self.accepted:
            self.filtered.append(entry)
            self.verbose_details('Filtered %s' % entry['title'])

    def reject(self, entry):
        """Reject this entry immediattely and permanently."""
        # schedule immediately filtering after this module has done execution
        if not entry in self.rejected:
            self.rejected.append(entry)
            self.verbose_details('Rejected %s' % entry['title'])

    def fail(self, entry):
        """Mark entry as failed."""
        logging.debug("Marking entry '%s' as failed" % entry['title'])
        if not entry in self.failed:
            self.failed.append(entry)
            self.manager.add_failed(entry)
            self.verbose_details('Failed %s' % entry['title'])

    def get_succeeded_entries(self):
        """Return set containing successfull entries"""
        # TODO: isn't feed.entries always only succeeded since failed are purged between modules?!
        succeeded = []
        for entry in self.entries:
            if not entry in self.failed:
                succeeded.append(entry)
        return succeeded

    def abort(self):
        """Abort this feed execution, no more modules will be executed."""
        self.__abort = True
        self.verbose_details('Aborting feed')

    def get_input_url(self, keyword):
        # TODO: move to better place?
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

    def __set_namespace(self, name):
        """Switch namespace in session"""
        self.cache.set_namespace(name)
        self.shared_cache.set_namespace(name)

    def __run_modules(self, event):
        """Execute module callbacks by event type if module is configured for this feed."""
        modules = self.manager.get_modules_by_event(event)
        # Sort modules based on module order.
        # Order can be also configured in which case given value overwrites module default.
        modules.sort(self.__sort_modules)
        for module in modules:
            keyword = module['keyword']
            if self.config.has_key(keyword) or (module['builtin'] and not self.config.get('disable_builtins', False)):
                # set cache namespaces to this module realm
                self.__set_namespace(keyword)
                # store execute info
                self.__current_event = event
                self.__current_module = keyword
                # call module
                try:
                    module['callback'](self)
                except Warning, w:
                    logging.warning(w)
                except Exception, e:
                    logging.exception('Unhandled error in module %s: %s' % (keyword, e))
                    self.abort()
                # check for priority operations
                if self.__abort: return
                self.__convert_entries()
                self.__purge_rejected()

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

    # TODO: all these verbose methods are confusing
    def verbose_progress(self, s):
        """Verboses progress, outputs only in non quiet mode."""
        # TODO: implement trough own logger?
        if not self.manager.options.quiet and not self.unittest:
          logging.info(s)
          
    def verbose_details(self, s):
        """Verbose if details option is enabled"""
        # TODO: implement trough own logger?
        if self.manager.options.details:
            try:
                print "+ %-8s %-12s %s" % (self.__current_event, self.__current_module, s)
            except:
                print "+ %-8s %-12s ERROR: Unable to print %s" % (self.__current_event, self.__current_module, repr(s))

    def verbose_details_entries(self):
        """If details option is enabled, print all produced entries"""
        if self.manager.options.details:
            for entry in self.entries:
                self.verbose_details('%s' % entry['title'])

    def resolvable(self, entry):
        """Return True if entry is resolvable by registered resolver."""
        for name, resolver in self.manager.resolvers.iteritems():
            if resolver.resolvable(self, entry):
                return True
        return False
        
    def resolve(self, entry):
        """Resolves given entry url. Raises ResolverException if resolve failed."""
        tries = 0
        while self.resolvable(entry):
            tries += 1
            if (tries > 300):
                raise ResolverException('Resolve was left in infinite loop while resolving %s, some resolver is returning True on resolvable method when it should not.' % entry['url'])
            for name, resolver in self.manager.resolvers.iteritems():
                if resolver.resolvable(self, entry):
                    logging.debug('%s resolving %s' % (name, entry['url']))
                    try:
                        resolver.resolve(self, entry)
                    except ResolverException, r:
                        # increase failcount
                        count = self.shared_cache.storedefault(entry['url'], 1)
                        count += 1
                        raise ResolverException('%s: %s' % (name, r.value))
                    except Exception, e:
                        logging.exception(e)
                        raise ResolverException('%s: Internal error with url %s' % (name, entry['url']))

    def _resolve_entries(self):
        """Resolves all entries in feed. Since this causes many requests to sites, use with caution."""
        for entry in self.entries:
            try:
                self.resolve(entry)
            except ResolverException, e:
                logging.warn(e.value)
                self.fail(entry)
    
    def execute(self):
        """Execute this feed, runs events in order of events array."""
        for event in self.manager.EVENTS[:-1]:
            # when learning, skip few events
            if self.manager.options.learn:
                if event in ['download', 'output']: 
                    # log keywords not executed
                    modules = self.manager.get_modules_by_event(event)
                    for module in modules:
                        if self.config.has_key(module['keyword']):
                            logging.info('Note: Feed %s keyword %s not executed due learn / reset.' % (self.name, module['keyword']))
                    continue
            # handle resolve event a bit special
            if event == 'resolve' and not self.unittest:
                self.__set_namespace('resolve')
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

    def terminate(self):
        """Execute terminate event for this feed"""
        if self.__abort: return
        self.__run_modules(self.manager.EVENTS[-1])

    def check_config(self):
        """Checks that feed configuration does not have mistyped modules"""
        def available(keyword):
            for event in self.manager.EVENTS:
                if self.manager.modules.get(event, {}).has_key(keyword):
                    return True
        for kw in self.config.keys():
            if kw in ['disable_builtins']:
                continue
            if not available(kw):
                logging.warning('Feed %s has unknown module %s' % (self.name, kw))

    def validate(self):
        """Module configuration validation."""
        for kw, value in self.config.iteritems():
            modules = self.manager.get_modules_by_keyword(kw)
            for module in modules:
                if hasattr(module['instance'], 'validate'):
                    errors = module['instance'].validate(self.config[kw])
                    if not errors:
                        print '%s passed' % kw
                    else:
                        print '%s failed:' % kw
                        for error in errors:
                            print error
                else:
                    logging.warning('Used module %s does not support validating' % kw)

