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
            # reading value should update "stored" date .. TODO: refactor stored -> access & days -> keep?
            item['stored'] = datetime.today().strftime('%Y-%m-%d')
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
        
        # You should NOT change these arrays at any point, and in most cases not even read them!
        # Mainly public since unittest needs these
        
        self.accepted = [] # accepted entries are always accepted, filtering does not affect them
        self.filtered = [] # filtered entries
        self.rejected = [] # rejected entries are removed unconditionally, even if accepted
        self.failed = []

        # flags and counters
        self.unittest = False
        self.__abort = False
        self.__purged = 0
        
        # state
        self.__current_event = None
        self.__current_module = None
        
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

    def abort(self):
        """Abort this feed execution, no more modules will be executed."""
        if not self.__abort:
            logging.info('Aborting feed %s' % self.name)
        self.__abort = True

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
        if isinstance(self.config[keyword], dict):
            if not self.config[keyword].has_key('url'):
                raise Exception('Input %s has invalid configuration, url is missing.' % keyword)
            return self.config[keyword]['url']
        else:
            return self.config[keyword]

    def log_once(self, s, log=logging):
        """Log string s once"""
        import md5
        m = md5.new()
        m.update(s)
        sum = m.hexdigest()
        seen = self.shared_cache.get('log-%s' % sum, False)
        if (seen): return
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
        for name, resolver in self.manager.get_resolvers().iteritems():
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
            for name, resolver in self.manager.get_resolvers().iteritems():
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
            
    def __get_priority(self, module, event):
        """Return order for module in this feed. Uses default value if no value is configured."""
        print repr(module)
        priority = module.get('priorities', {}).get('event', 0)
        keyword = module['name']
        if self.config.has_key(keyword):
            if isinstance(self.config[keyword], dict):
                order = self.config[keyword].get('priority', priority)
        return priority

    def __sort_modules(self, a, b, event):
        a = self.__get_priority(a, event)
        b = self.__get_priority(b, event)
        return cmp(a, b)

    def __set_namespace(self, name):
        """Switch namespace in session"""
        self.cache.set_namespace(name)
        self.shared_cache.set_namespace(name)

    def __run_modules(self, event):
        """Execute module events if module is configured for this feed."""
        modules = self.manager.get_modules_by_event(event)
        # Sort modules based on module event priority
        # Priority can be also configured in which case given value overwrites module default.
        modules.sort(lambda x,y: self.__sort_modules(x,y, event), reverse=True)

        for module in modules:
            keyword = module['name']
            if self.config.has_key(keyword) or (module['builtin'] and not self.config.get('disable_builtins', False)):
                # set cache namespaces to this module realm
                self.__set_namespace(keyword)
                # store execute info
                self.__current_event = event
                self.__current_module = keyword
                # call module
                try:
                    method = self.manager.get_method_for_event(event)
                    getattr(module['instance'], method)(self)
                except Warning, w: # TODO: refactor into ModuleWarning
                    logging.warning(w)
                except Exception, e:
                    logging.exception('Unhandled error in module %s: %s' % (keyword, e))
                    self.abort()
                # check for priority operations
                self.__purge_rejected()
                self.__purge_failed()
                if self.__abort: return

    
    def execute(self):
        """Execute this feed, runs events in order of events array."""
        # validate configuration
        errors = self.validate()
        if errors:
            logging.critical('Feed \'%s\' has configuration errors:' % self.name)
            for error in errors:
                logging.error(error)
            if not self.manager.options.validate:
                self.abort()
            return
        # do not execute in validate mode
        if self.manager.options.validate:
            if not errors:
                logging.info('Feed \'%s\' passed' % self.name)
            return
        # run events
        for event in self.manager.EVENTS[:-1]:
            # skip resolve if in unittest
            if event == 'resolve' and not self.unittest:
                self.__set_namespace('resolve')
                self._resolve_entries()
                self.__purge_failed()
            if event == 'resolve': continue
            # when learning, skip few events
            if self.manager.options.learn:
                if event in ['download', 'output']: 
                    # log keywords not executed
                    modules = self.manager.get_modules_by_event(event)
                    for module in modules:
                        if self.config.has_key(module['keyword']):
                            logging.info('Feed %s keyword %s is not executed because of learn/reset.' % (self.name, module['keyword']))
                    continue
            # run all modules with this event
            self.__run_modules(event)
            # purge filtered entries between events
            # rejected and failed entries are purged between modules
            self._purge()
            # verbose some progress
            if event == 'input':
                self.verbose_details_entries()
                self.verbose_progress('Feed %s produced %s entries.' % (self.name, len(self.entries)))
            if event == 'filter':
                self.verbose_progress('Feed %s filtered %s entries (%s remains).' % (self.name, self.__purged, len(self.entries)))
            # if abort flag has been set feed should be aborted now
            if self.__abort:
                return

    def terminate(self):
        """Execute terminate event for this feed"""
        if self.__abort: return
        self.__run_modules(self.manager.EVENTS[-1])

    def validate(self):
        """Module configuration validation. Return array of error messages that were detected."""
        validate_errors = []
        # validate all modules
        for kw, value in self.config.iteritems():
            module = self.manager.modules.get(kw)
            if not module:
                validate_errors.append('unknown keyword \'%s\'' % kw)
                continue
            if hasattr(module['instance'], 'validate'):
                errors = module['instance'].validate(self.config[kw])
                if errors:
                    for error in errors:
                        validate_errors.append('%s %s' % (kw, error))
            else:
                logging.warning('Used module %s does not support validating. Please notify author!' % kw)
        return validate_errors