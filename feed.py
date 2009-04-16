import logging
from datetime import datetime
from manager import PluginWarning
from utils.simple_persistence import SimplePersistence

log = logging.getLogger('feed')

class Entry(dict):

    """
        Represents one item in feed. Must have url and title fields.
        See. http://flexget.com/wiki/DevelopersEntry

        Internally stored original_url is necessary because
        plugins (ie. resolvers) may change this into something else 
        and otherwise that information would be lost.
    """

    def __init__(self, *args):
        if len(args) == 2:
            self['title'] = args[0]
            self['url'] = args[1]

    def __setitem__(self, key, value):
        if key == 'url':
            if not 'original_url' in self:
                self['original_url'] = value
        dict.__setitem__(self, key, value)
    
    def safe_str(self):
        return "%s | %s" % (self['title'], self['url'])

    def isvalid(self):
        """Return True if entry is valid. Return False if this cannot be used."""
        if not 'title' in self:
            return False
        if not 'url' in self:
            return True
        return True

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
        self.session = None

        
        # simple persistence
        self.simple_persistence = SimplePersistence(self)
        
        # undecided entries in the feed (created by input)
        self.entries = []
        
        # You should NOT change these arrays, use reject / accept methods!
        
        self.accepted = [] # accepted entries, can still be rejected
        self.rejected = [] # rejected entries
        self.failed = []

        # TODO: feed.abort() should be done by using exception? not a flag that has to be checked everywhere

        # flags and counters
        self.__abort = False
        self.__purged = 0
        
        # current state
        self.current_event = None
        self.current_plugin = None
        
    def _purge(self):
        log.critical('plugin %s called deprecated method feed._purge' % self.current_plugin)

    def __purge_failed(self):
        """Purge failed entries from feed."""
        self.__purge(self.failed, [], False)

    def __purge_rejected(self):
        """Purge rejected entries from feed."""
        self.__purge(self.rejected)

    def __purge(self, entries, not_in_list=[], count=True):
        """Purge entries in list from feed.entries"""
        for entry in self.entries[:]:
            if entry in entries and entry not in not_in_list:
                #log.debug('Purging entry %s' % entry.safe_str())
                self.entries.remove(entry)
                if count:
                    self.__purged += 1

    def accept(self, entry, reason=None):
        """Accepts this entry."""
        if not entry in self.accepted:
            self.accepted.append(entry)
            self.verbose_details('Accepted %s' % entry['title'], reason)

    # TODO: remove at some point
    def filter(self, entry, reason=None):
        log.critical('plugin %s called deprecated method feed.filter' % self.current_plugin)

    def reject(self, entry, reason=None):
        """Reject this entry immediately and permanently."""
        # schedule immediately filtering after this plugin has done execution
        if not entry in self.rejected:
            self.rejected.append(entry)
            self.verbose_details('Rejected %s' % entry['title'], reason)
        # TODO: HACK
        if entry in self.accepted:
            self.accepted.remove(entry)

    def fail(self, entry, reason=None):
        """Mark entry as failed."""
        log.debug("Marking entry '%s' as failed" % entry['title'])
        if not entry in self.failed:
            self.failed.append(entry)
            self.manager.add_failed(entry)
            self.verbose_details('Failed %s' % entry['title'], reason)

    def abort(self, **kwargs):
        """Abort this feed execution, no more plugins will be executed."""
        if not self.__abort and not kwargs.get('silent', False):
            log.info('Aborting feed %s' % self.name)
        self.__abort = True
        self.__run_event('abort')

    def find_entry(self, category='entries', **values):
        """Find and return entry with given attributes from feed or None"""
        cat = getattr(self, category)
        if not isinstance(cat, list):
            raise TypeError('category must be a list')
        for entry in cat:
            match = 0
            for k, v in values.iteritems():
                if entry.has_key(k):
                    if entry.get(k) == v: 
                        match += 1
            if match==len(values):
                return entry
        return None

    def get_input_url(self, keyword):
        # TODO: move to better place?
        """
            Helper method for plugins. Return url for a specified keyword.
            Supports configuration in following forms:
                <keyword>: <address>
            and
                <keyword>:
                    url: <address>
        """
        if isinstance(self.config[keyword], dict):
            if not 'url' in self.config[keyword]:
                raise Exception('Input %s has invalid configuration, url is missing.' % keyword)
            return self.config[keyword]['url']
        else:
            return self.config[keyword]

    # TODO: all these verbose methods are confusing
    def verbose_progress(self, s, logger=log):
        """Verbose progress, outputs only in non quiet mode."""
        # TODO: implement trough own logger?
        if not self.manager.options.quiet and not self.manager.unit_test:
            logger.info(s)
          
    def verbose_details(self, msg, reason=''):
        """Verbose if details option is enabled"""
        # TODO: implement trough own logger?
        if self.manager.options.details:
            try:
                reason_str = ''
                if reason:
                    reason_str = ' (%s)' % reason
                print "+ %-8s %-12s %s%s" % (self.current_event, self.current_plugin, msg, reason_str)
            except:
                print "+ %-8s %-12s ERROR: Unable to print %s" % (self.current_event, self.current_plugin, repr(msg))

    def verbose_details_entries(self):
        """If details option is enabled, print all produced entries"""
        if self.manager.options.details:
            for entry in self.entries:
                self.verbose_details('%s' % entry['title'])
            
    def __run_event(self, event):
        """Execute plugin events if plugin is configured for this feed."""
        plugins = self.manager.get_plugins_by_event(event)

        for plugin in plugins:
            keyword = plugin['name']
            if keyword in self.config or plugin['builtin']:
                # store execute info
                self.current_event = event
                self.current_plugin = keyword
                # call the plugin
                try:
                    method = self.manager.event_methods[event]
                    getattr(plugin['instance'], method)(self)
                except PluginWarning, warn:
                    # this warning should be logged only once (may keep repeating)
                    if warn.kwargs.get('log_once', False):
                        from utils.log import log_once
                        log_once(warn, warn.log)
                    else:
                        warn.log.warning(warn)
                except Exception, e:
                    log.exception('Unhandled error in plugin %s: %s' % (keyword, e))
                    self.abort()
                # remove entries
                self.__purge_rejected()
                self.__purge_failed()
                # check for priority operations
                if self.__abort: return
    
    def execute(self):
        """Execute this feed, runs events in order of events array."""
        # validate configuration
        errors = self.validate()
        if self.__abort: return
        if self.manager.options.validate:
            if not errors:
                print 'Feed \'%s\' passed' % self.name
                return
            
        # run events
        for event in self.manager.events:
            # when learning, skip few events
            if self.manager.options.learn:
                if event in ['download', 'output']: 
                    # log keywords not executed
                    plugins = self.manager.get_plugins_by_event(event)
                    for plugin in plugins:
                        if plugin['name'] in self.config:
                            log.info('Feed %s keyword %s is not executed because of learn/reset.' % (self.name, plugin['name']))
                    continue
            # run all plugins with this event
            self.__run_event(event)
            # TODO: should we purge rejected and failed between events?
            
            # verbose some progress
            if event == 'input':
                self.verbose_details_entries()
                if not self.entries:
                    self.verbose_progress('Feed %s didn\'t produce any entries. This is likely to be miss configured or non-functional input.' % self.name)
                else:
                    self.verbose_progress('Feed %s produced %s entries.' % (self.name, len(self.entries)))
            if event == 'filter':
                self.verbose_progress('Feed %s filtered %s entries (%s remains).' % (self.name, self.__purged, len(self.entries)))
            # if abort flag has been set feed should be aborted now
            if self.__abort:
                return


    def process_start(self):
        """Execute process_start event"""
        self.__run_event('process_start')

    def process_end(self):
        """Execute terminate event for this feed"""
        if self.__abort: return
        self.__run_event('process_end')

    def validate(self):
        """Plugin configuration validation. Return array of error messages that were detected."""
        validate_errors = []
        # validate all plugins
        for keyword in self.config:
            plugin = self.manager.plugins.get(keyword)
            if not plugin:
                validate_errors.append('Unknown plugin \'%s\'' % keyword)
                continue
            if hasattr(plugin['instance'], 'validator'):
                try:
                    validator = plugin['instance'].validator()
                except TypeError:
                    log.critical('invalid validator method in plugin %s' % keyword)
                    continue
                if not validator.validate(self.config[keyword]):
                    for msg in validator.errors.messages:
                        validate_errors.append('%s %s' % (keyword, msg))
            else:
                log.warning('Used plugin %s does not support validating. Please notify author!' % keyword)
                
        # log errors and abort
        if validate_errors:
            log.critical('Feed \'%s\' has configuration errors:' % self.name)
            for error in validate_errors:
                log.error(error)
            # feed has errors, abort it
            self.abort()
                
        return validate_errors