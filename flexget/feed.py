import hashlib
import logging
from flexget.manager import Session
from flexget.plugin import get_methods_by_event, get_plugins_by_event, get_plugin_by_name, \
    FEED_EVENTS, PluginWarning, PluginError, PluginDependencyError
from flexget.utils.simple_persistence import SimplePersistence
from flexget.event import fire_event

log = logging.getLogger('feed')


class EntryUnicodeError(Exception):

    """This exception is thrown when trying to set non-unicode compatible field value to entry"""

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __str__(self):
        return 'Field %s is not unicode-compatible (%s)' % (self.key, repr(self.value))


class Entry(dict):
    """
        Represents one item in feed. Must have url and title fields.
        See. http://flexget.com/wiki/DevelopersEntry

        Internally stored original_url is necessary because
        plugins (ie. resolvers) may change this into something else
        and otherwise that information would be lost.
    """

    def __init__(self, *args):
        self.trace = []
        if len(args) == 2:
            self['title'] = args[0]
            self['url'] = args[1]

    def __setitem__(self, key, value):
        # enforce unicode compatibility
        if isinstance(value, str):
            try:
                value = unicode(value)
            except UnicodeDecodeError:
                raise EntryUnicodeError(key, value)

        # url and original_url handling
        if key == 'url':
            if not 'original_url' in self:
                self['original_url'] = value
            if not isinstance(value, basestring):
                raise PluginError('Tried to set %s url to %s' % \
                    (repr(self.get('title')), repr(value)))

        # title handling
        if key == 'title':
            if not isinstance(value, basestring):
                raise PluginError('Tried to set title to %s' % \
                    (repr(value)))

        # TODO: HACK! Implement via plugin once #348 (entry events) is implemented
        # enforces imdb_url in same format
        if key == 'imdb_url':
            from flexget.utils.imdb import extract_id
            value = u'http://www.imdb.com/title/%s/' % extract_id(value)

        log.log(5, 'ENTRY %s = %s' % (key, value))

        dict.__setitem__(self, key, value)

        # calculate uid
        if self.get('title') and self.get('original_url'):
            m = hashlib.md5()

            def just_fucking_do_it(value):
                if isinstance(value, unicode):
                    m.update(value.encode('ascii', 'ignore'))
                else:
                    m.update(value)

            just_fucking_do_it(self['original_url'])
            just_fucking_do_it(self['title'])
            uid = m.hexdigest()
            dict.__setitem__(self, 'uid', uid)

    def safe_str(self):
        return '%s | %s' % (self['title'], self['url'])

    def isvalid(self):
        """Return True if entry is valid. Return False if this cannot be used."""
        if not 'title' in self:
            return False
        if not 'url' in self:
            return False
        if not isinstance(self['url'], basestring):
            return False
        if not isinstance(self['title'], basestring):
            return False
        return True


def useFeedLogging(func):

    def wrapper(self, *args, **kw):
        # Set the feed name in the logger
        from flexget import logger
        logger.set_feed(self.name)
        try:
            return func(self, *args, **kw)
        finally:
            logger.set_feed('')

    return wrapper


class Feed(object):

    def __init__(self, manager, name, config):
        """Represents one feed in configuration.

        :name: name of the feed
        :config: feed configuration (dict)

        Fires events:

        feed.execute.before_plugin:
          Before a plugin is about to be executed. Note that since this will also include all
          builtin plugins the amount of calls can be quite high

          parameters: feed, keyword

        feed.execute.after_plugin:
          After a plugin has been executed.

          parameters: feed, keyword

        feed.execute.completed:
          After feed execution has been completed

          parameters: feed
        """
        self.name = unicode(name)
        self.config = config
        self.manager = manager

        # simple persistence
        self.simple_persistence = SimplePersistence(self)

        # use reset to init variables when creating
        self._reset()

    def _reset(self):
        """Reset feed state"""
        log.debug('reseting')
        self.enabled = True
        self.session = None
        self.priority = 65535

        # undecided entries in the feed (created by input)
        self.entries = []

        # You should NOT change these arrays, use reject, accept and fail methods!
        self.accepted = [] # accepted entries, can still be rejected
        self.rejected = [] # rejected entries
        self.failed = []   # failed entries

        # TODO: feed.abort() should be done by using exception? not a flag that has to be checked everywhere

        # flags and counters
        self._abort = False
        self.__purged = 0

        # current state
        self.current_event = None
        self.current_plugin = None

    def __cmp__(self, other):
        return cmp(self.priority, other.priority)

    def __str__(self):
        return '<Feed(name=%s,aborted=%s)>' % (self.name, str(self._abort))

    def purge(self):
        """
            Purge rejected and failed entries.
            Failed entries will be removed from entries, accepted and rejected
            Rejected entries will be removed from entries and accepted
        """
        self.__purge_failed()
        self.__purge_rejected()

    def __purge_failed(self):
        """Purge failed entries from feed."""
        self.__purge(self.failed, self.entries, False)
        self.__purge(self.failed, self.rejected, False)
        self.__purge(self.failed, self.accepted, False)

    def __purge_rejected(self):
        """Purge rejected entries from feed."""
        self.__purge(self.rejected, self.entries)
        self.__purge(self.rejected, self.accepted)

    def __purge(self, purge_what, purge_from, count=True):
        """Purge entries in list from feed.entries"""
        for entry in purge_what:
            if entry in purge_from:
                purge_from.remove(entry)
                if count:
                    self.__purged += 1

    def accept(self, entry, reason=None):
        """Accepts this entry with optional reason."""
        if not isinstance(entry, Entry):
            raise Exception('Trying to accept non entry, %s' % repr(entry))
        if entry in self.rejected:
            log.debug('tried to accept rejected %s' % repr(entry))
        if entry not in self.accepted and entry not in self.rejected:
            self.accepted.append(entry)
            # store metainfo into entry (plugin in the future?)
            entry.pop('reason', None) # remove old reason by previous state
            if reason:
                entry['reason'] = reason
            entry['accepted_by'] = self.current_plugin
            # Run on_entry_accept event
            self.__run_event('accept', entry, reason)

    def reject(self, entry, reason=None):
        """Reject this entry immediately and permanently with optional reason"""
        if not isinstance(entry, Entry):
            raise Exception('Trying to reject non entry, %s' % repr(entry))
        # ignore rejections on immortal entries
        if entry.get('immortal'):
            reason_str = ''
            if reason:
                reason_str = '(%s)' % reason
            log.info('Tried to reject immortal %s %s' % (entry['title'], reason_str))
            return

        if not entry in self.rejected:
            self.rejected.append(entry)
            # Run on_entry_reject event
            self.__run_event('reject', entry, reason)
        # store metainfo into entry (plugin in the future?)
        entry.pop('reason', None) # remove old reason by previous state
        if reason:
            entry['reason'] = reason
        entry['rejected_by'] = self.current_plugin

    def fail(self, entry, reason=None):
        """Mark entry as failed."""
        log.debug('Marking entry \'%s\' as failed' % entry['title'])
        if not entry in self.failed:
            self.failed.append(entry)
            log.error('Failed %s (%s)' % (entry['title'], reason))
            # Run on_entry_fail event
            self.__run_event('fail', entry=entry, reason=reason)

    def trace(self, entry, message):
        """Add tracing message to entry."""
        entry.trace.append((self.current_plugin, message))

    def abort(self, **kwargs):
        """Abort this feed execution, no more plugins will be executed."""
        if self._abort:
            return
        if not kwargs.get('silent', False):
            log.info('Aborting feed (plugin: %s)' % (self.current_plugin))
        log.debug('Aborting feed (plugin: %s)' % (self.current_plugin))
        # Run the abort event before we set the _abort flag
        self._abort = True
        self.__run_event('abort')

    def find_entry(self, category='entries', **values):
        """Find and return entry with given attributes from feed or None"""
        cat = getattr(self, category)
        if not isinstance(cat, list):
            raise TypeError('category must be a list')
        for entry in cat:
            match = 0
            for k, v in values.iteritems():
                if k in entry:
                    if entry.get(k) == v:
                        match += 1
            if match == len(values):
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
                raise PluginError('Input %s has invalid configuration, url is missing.' % keyword)
            return self.config[keyword]['url']
        else:
            return self.config[keyword]

    # TODO: all these verbose methods are confusing
    def verbose_progress(self, s, logger=log):
        """Verbose progress, outputs only without --cron or -q"""
        # TODO: implement trough own logger?
        if not self.manager.options.quiet and not self.manager.unit_test:
            logger.info(s)

    def __run_event(self, event, entry=None, reason=None):
        """Execute all configured plugins in :event:"""
        entry_events = ['accept', 'reject', 'fail']
        # fail when trying to run an on_entry_* event without an entry
        if event in entry_events and not entry:
            raise Exception('Entry must be specified when running the %s event' % event)
        methods = get_methods_by_event(event)
        # log.log(5, 'Event %s methods %s' % (event, methods))

        # warn if no filters or outputs in the feed
        if event in ['filter', 'output']:
            for method in methods:
                if method.plugin.name in self.config:
                    break
            else:
                if not self.manager.unit_test:
                    log.warning('Feed doesn\'t have any %s plugins, you should add some!' % (event))

        for method in methods:
            keyword = method.plugin.name
            if keyword in self.config or method.plugin.builtin:

                if event not in entry_events:
                    # store execute info, except during entry events
                    self.current_event = event
                    self.current_plugin = keyword

                # log.log(5, 'Running %s method %s' % (keyword, method))
                # call the plugin
                try:
                    if event in entry_events:
                        # Add extra parameters for the on_entry_* events
                        method(self, entry, reason)
                    else:
                        fire_event('feed.execute.before_plugin', self, keyword)
                        try:
                            method(self)
                        finally:
                            fire_event('feed.execute.after_plugin', self, keyword)
                except PluginWarning, warn:
                    # check if this warning should be logged only once (may keep repeating)
                    if warn.kwargs.get('log_once', False):
                        from flexget.utils.log import log_once
                        log_once(warn.value, warn.log)
                    else:
                        warn.log.warning(warn)
                except EntryUnicodeError, eue:
                    log.critical('Plugin %s tried to create non-unicode compatible entry (key: %s, value: %s)' % \
                        (keyword, eue.key, repr(eue.value)))
                    self.abort()
                except PluginError, err:
                    err.log.critical(err)
                    self.abort()
                except PluginDependencyError, e:
                    log.critical('Plugin %s has requested another plugin %s which is not available.' % \
                        (self.current_plugin, e.plugin))
                    self.abort()
                except Exception, e:
                    log.exception('Unhandled error in plugin %s: %s' % (keyword, e))
                    self.abort()
                    # don't handle plugin errors gracefully with unit test
                    if self.manager.unit_test:
                        raise

                if event not in entry_events:
                    # purge entries between plugins
                    self.purge()
                # check for priority operations
                if self._abort and event != 'abort':
                    return

    @useFeedLogging
    def execute(self):
        """Execute this feed"""

        log.debug('excecuting %s' % self.name)

        self._reset()

        # validate configuration
        errors = self.validate()
        if self._abort: # todo: bad practice
            return
        if errors and self.manager.unit_test: # todo: bad practice
            raise Exception('configuration errors')
        if self.manager.options.validate:
            if not errors:
                print 'Feed \'%s\' passed' % self.name
            return

        log.debug('starting session')
        self.session = Session()

        try:
            # run events
            for event in FEED_EVENTS:
                # when learning, skip few events
                if self.manager.options.learn:
                    if event in ['download', 'output']:
                        # log keywords not executed
                        plugins = get_plugins_by_event(event)
                        for plugin in plugins:
                            if plugin.name in self.config:
                                log.info('Plugin %s is not executed because of --learn / --reset' % (plugin.name))
                        continue

                # run all plugins with this event
                self.__run_event(event)

                # if abort flag has been set feed should be aborted now
                if self._abort:
                    return

            log.debug('committing session, abort=%s' % self._abort)
            self.session.commit()
            fire_event('feed.execute.completed', self)
        except:
            log.debug('db rollback on exception')
            self.session.close()
            raise

    def process_start(self):
        """Execute process_start event"""
        self.__run_event('process_start')

    def process_end(self):
        """Execute terminate event for this feed"""
        if self.manager.options.validate:
            log.debug('No process_end event with --check')
            return
        self.__run_event('process_end')

    def validate(self):
        """Called during feed execution. Validates config, prints errors and aborts feed if invalid."""
        errors = self.validate_config(self.config)
        # log errors and abort
        if errors:
            log.critical('Feed \'%s\' has configuration errors:' % self.name)
            for error in errors:
                log.error(error)
            # feed has errors, abort it
            self.abort()
        return errors

    @staticmethod
    def validate_config(config):
        """Plugin configuration validation. Return list of error messages that were detected."""
        validate_errors = []
        # validate config is a dictionary
        if not isinstance(config, dict):
            validate_errors.append('Config is not a dictionary.')
            return validate_errors
        # validate all plugins
        for keyword in config:
            if keyword.startswith('_'):
                continue
            try:
                plugin = get_plugin_by_name(keyword)
            except:
                validate_errors.append('Unknown plugin \'%s\'' % keyword)
                continue
            if hasattr(plugin.instance, 'validator'):
                try:
                    validator = plugin.instance.validator()
                except TypeError, e:
                    log.critical('Invalid validator method in plugin %s' % keyword)
                    log.exception(e)
                    continue
                if not validator.name == 'root':
                    # if validator is not root type, add root validator as it's parent
                    validator = validator.add_root_parent()
                if not validator.validate(config[keyword]):
                    for msg in validator.errors.messages:
                        validate_errors.append('%s %s' % (keyword, msg))
            else:
                log.warning('Used plugin %s does not support validating. Please notify author!' % keyword)

        return validate_errors
