import logging
import copy
from flexget.manager import Session
from flexget.plugin import get_plugins_by_phase, get_plugin_by_name, \
    feed_phases, PluginWarning, PluginError, DependencyError, plugins as all_plugins
from flexget.utils.simple_persistence import SimpleFeedPersistence
from flexget.event import fire_event

log = logging.getLogger('feed')


class EntryUnicodeError(Exception):

    """This exception is thrown when trying to set non-unicode compatible field value to entry"""

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __str__(self):
        return 'Field %s is not unicode-compatible (%r)' % (self.key, self.value)


class LazyField(object):
    """Stores a callback function to populate entry fields. Runs it when called or to get a string representation."""

    def __init__(self, entry, field, func):
        self.entry = entry
        self.field = field
        self.func = func

    def __call__(self):
        return self.func(self.entry, self.field)

    def __str__(self):
        return str(self())

    def __unicode__(self):
        return unicode(self())


class Entry(dict):
    """
        Represents one item in feed. Must have url and title fields.
        See. http://flexget.com/wiki/DevelopersEntry

        Internally stored original_url is necessary because
        plugins (ie. resolvers) may change this into something else
        and otherwise that information would be lost.
    """

    def __init__(self, *args, **kwargs):
        # Store kwargs into our internal dict
        if len(args) == 2:
            kwargs['title'] = args[0]
            kwargs['url'] = args[1]
            args = []
        dict.__init__(self, *args, **kwargs)
        self.trace = []
        self.snapshots = {}

    def __setitem__(self, key, value):
        # enforce unicode compatibility
        if isinstance(value, str):
            try:
                value = unicode(value)
            except UnicodeDecodeError:
                raise EntryUnicodeError(key, value)

        # url and original_url handling
        if key == 'url':
            if not isinstance(value, basestring):
                raise PluginError('Tried to set %r url to %r' % (self.get('title'), value))
            if not 'original_url' in self:
                self['original_url'] = value

        # title handling
        if key == 'title':
            if not isinstance(value, basestring):
                raise PluginError('Tried to set title to %r' % value)

        # TODO: HACK! Implement via plugin once #348 (entry events) is implemented
        # enforces imdb_url in same format
        if key == 'imdb_url' and isinstance(value, basestring):
            from flexget.utils.imdb import extract_id, make_url
            imdb_id = extract_id(value)
            if imdb_id:
                value = make_url(imdb_id)
            else:
                log.debug('Tried to set imdb_id to invalid imdb url: %s' % value)
                value = None

        try:
            log.debugall('ENTRY %s = %r' % (key, value))
        except Exception, e:
            log.debug('trying to debug key `%s` value threw exception: %s' % (key, e))

        dict.__setitem__(self, key, value)

    def __getitem__(self, key):
        """Supports lazy loading of fields. If a stored value is a LazyField, call it, return the result."""
        result = dict.__getitem__(self, key)
        if isinstance(result, LazyField):
            return result()
        else:
            return result

    def get(self, key, default=None):
        """Overridden so that our __getitem__ gets used for LazyFields"""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        """Will cause lazy field lookup to occur and will return false if a field exists but is None."""
        return self.get(key) is not None

    def register_lazy_fields(self, fields, func):
        """Register a list of fields to be lazily loaded by callback func.

        Args:
            fields: List of field names that are registered as lazy fields
            func: Callback function which is called when lazy field needs to be evaluated.
                  Function call will get params (entry, field). See `LazyField` class for more details.
        """
        for field in fields:
            if not self.get_no_lazy(field):
                self[field] = LazyField(self, field, func)

    def is_lazy(self, field):
        """Returns True if field is lazy loading."""
        return isinstance(dict.get(self, field), LazyField)

    def get_no_lazy(self, field, default=None):
        """Gets the value of a field if it is not a lazy field."""
        if self.is_lazy(field):
            return default
        return self.get(field, default)

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

    def take_snapshot(self, name):
        snapshot = {}
        for field, value in self.iteritems():
            try:
                snapshot[field] = copy.deepcopy(value)
            except TypeError:
                log.warning('Unable to take `%s` snapshot for field `%s` in `%s`' % (name, field, self['title']))
        if snapshot:
            if name in self.snapshots:
                log.warning('Snapshot `%s` is being overwritten for `%s`' % (name, self['title']))
            self.snapshots[name] = snapshot

    def update_using_map(self, field_map, source_item):
        """Populates entry fields from a source object using a dictionary that maps from entry field names to
        attribute of the source object.

        Args:
            field_map: A dictionary mapping entry field names to the attribute in source_item (nested attributes
                are also supported, separated by a dot,) or a function that takes source_item as an argument
            source_item: Source of information to be used by the map
        """

        for field, value in field_map.iteritems():
            if isinstance(value, basestring):
                self[field] = reduce(getattr, value.split('.'), source_item)
            else:
                self[field] = value(source_item)


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

    max_reruns = 5

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
        self.simple_persistence = SimpleFeedPersistence(self)

        # not to be reseted
        self._rerun_count = 0

        # use reset to init variables when creating
        self._reset()

    def _reset(self):
        """Reset feed state"""
        log.debug('resetting %s' % self.name)
        self.enabled = True
        self.session = None
        self.priority = 65535

        # undecided entries in the feed (created by input)
        self.entries = []

        # You should NOT change these arrays, use reject, accept and fail methods!
        self.accepted = [] # accepted entries, can still be rejected
        self.rejected = [] # rejected entries
        self.failed = []   # failed entries

        self.disabled_phases = []

        # TODO: feed.abort() should be done by using exception? not a flag that has to be checked everywhere
        self._abort = False

        self._rerun = False

        # current state
        self.current_phase = None
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
        self.__purge(self.failed, self.entries)
        self.__purge(self.failed, self.rejected)
        self.__purge(self.failed, self.accepted)

    def __purge_rejected(self):
        """Purge rejected entries from feed."""
        self.__purge(self.rejected, self.entries)
        self.__purge(self.rejected, self.accepted)

    def __purge(self, purge_what, purge_from):
        """Purge entries in list from feed.entries"""
        # TODO: there is probably more efficient way to do this now that I got rid of __count
        for entry in purge_what:
            if entry in purge_from:
                purge_from.remove(entry)

    def disable_phase(self, phase):
        """Disable :phase: from execution.

        All disabled phases are re-enabled after feed execution has been completed.
        See self._reset()
        """
        if phase not in feed_phases:
            raise ValueError('%s is not a valid phase' % phase)
        if phase not in self.disabled_phases:
            log.debug('Disabling %s phase' % phase)
            self.disabled_phases.append(phase)

    def accept(self, entry, reason=None, **kwargs):
        """Accepts this entry with optional reason."""
        if not isinstance(entry, Entry):
            raise Exception('Trying to accept non entry, %r' % entry)
        if entry in self.rejected:
            log.debug('tried to accept rejected %r' % entry)
        if entry not in self.accepted and entry not in self.rejected:
            self.accepted.append(entry)
            # Run on_entry_accept phase
            self.__run_entry_phase('accept', entry, reason=reason, **kwargs)

    def reject(self, entry, reason=None, **kwargs):
        """Reject this entry immediately and permanently with optional reason"""
        if not isinstance(entry, Entry):
            raise Exception('Trying to reject non entry, %r' % entry)
        # ignore rejections on immortal entries
        if entry.get('immortal'):
            reason_str = '(%s)' % reason if reason else ''
            log.info('Tried to reject immortal %s %s' % (entry['title'], reason_str))
            self.trace(entry, 'Tried to reject immortal %s' % reason_str)
            return

        if not entry in self.rejected:
            self.rejected.append(entry)
            # Run on_entry_reject phase
            self.__run_entry_phase('reject', entry, reason=reason, **kwargs)

    def fail(self, entry, reason=None, **kwargs):
        """Mark entry as failed."""
        log.debug('Marking entry \'%s\' as failed' % entry['title'])
        if not entry in self.failed:
            self.failed.append(entry)
            log.error('Failed %s (%s)' % (entry['title'], reason))
            # Run on_entry_fail phase
            self.__run_entry_phase('fail', entry, reason=reason, **kwargs)

    def trace(self, entry, message):
        """Add tracing message to entry."""
        entry.trace.append((self.current_plugin, message))

    def abort(self, **kwargs):
        """Abort this feed execution, no more plugins will be executed."""
        if self._abort:
            return
        if not kwargs.get('silent', False):
            log.info('Aborting feed (plugin: %s)' % self.current_plugin)
        else:
            log.debug('Aborting feed (plugin: %s)' % self.current_plugin)
        # Run the abort phase before we set the _abort flag
        self._abort = True
        self.__run_feed_phase('abort')

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

    def plugins(self, phase=None):
        """An iterator over PluginInfo instances enabled on this feed.

        Args:
            phase: Limits to plugins enabled on given phase, sorted in phase order
        """
        if phase:
            plugins = sorted(get_plugins_by_phase(phase), key=lambda p: p.phase_handlers[phase], reverse=True)
        else:
            plugins = all_plugins.itervalues()
        return (p for p in plugins if p.name in self.config or p.builtin)

    def __run_feed_phase(self, phase):
        if phase not in feed_phases + ['abort', 'process_start', 'process_end']:
            raise Exception('%s is not a valid feed phase' % phase)
        # warn if no filters or outputs in the feed
        phase_plugins = self.plugins(phase)
        if phase in ['filter', 'output']:
            if not phase_plugins and not self.manager.unit_test:
                log.warning('Feed doesn\'t have any %s plugins, you should add some!' % phase)

        for plugin in phase_plugins:
            # Abort this phase if one of the plugins disables it
            if phase in self.disabled_phases:
                return
            # store execute info, except during entry events
            self.current_phase = phase
            self.current_plugin = plugin.name

            if plugin.api_ver == 1:
                # backwards compatibility
                # pass method only feed (old behaviour)
                args = (self,)
            else:
                # pass method feed, config
                args = (self, self.config.get(plugin.name))

            try:
                fire_event('feed.execute.before_plugin', self, plugin.name)
                response = self.__run_plugin(plugin, phase, args)
                if phase == 'input' and response:
                    # add entries returned by input to self.entries
                    self.entries.extend(response)
                # purge entries between plugins
                self.purge()
            finally:
                fire_event('feed.execute.after_plugin', self, plugin.name)

            # Make sure we abort if any plugin sets our abort flag
            if self._abort and phase != 'abort':
                return

    def __run_entry_phase(self, phase, entry, **kwargs):
        # TODO: entry events are not very elegant, refactor into real (new) events or something ...
        if phase not in ['accept', 'reject', 'fail']:
            raise Exception('Not a valid entry phase')
        phase_plugins = self.plugins(phase)
        for plugin in phase_plugins:
            self.__run_plugin(plugin, phase, (self, entry), kwargs)

    def __run_plugin(self, plugin, phase, args=None, kwargs=None):
        """Execute given plugin's phase method, with supplied args and kwargs."""

        keyword = plugin.name
        method = plugin.phase_handlers[phase]
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        # log.debugall('Running %s method %s' % (keyword, method))
        # call the plugin
        try:
            return method(*args, **kwargs)
        except PluginWarning, warn:
            # check if this warning should be logged only once (may keep repeating)
            if warn.kwargs.get('log_once', False):
                from flexget.utils.log import log_once
                log_once(warn.value, warn.log)
            else:
                warn.log.warning(warn)
        except EntryUnicodeError, eue:
            log.critical('Plugin %s tried to create non-unicode compatible entry (key: %s, value: %r)' %
                (keyword, eue.key, eue.value))
            self.abort()
        except PluginError, err:
            err.log.critical(err)
            self.abort()
        except DependencyError, e:
            log.critical('Plugin `%s` cannot be used because dependency `%s` is missing.' %
                (keyword, e.missing))
            self.abort()
        except Exception, e:
            log.exception('BUG: Unhandled error in plugin %s: %s' % (keyword, e))
            self.abort()
            # don't handle plugin errors gracefully with unit test
            if self.manager.unit_test:
                raise

    def rerun(self):
        """Immediattely re-run the feed after execute has completed."""
        self._rerun = True
        log.info('Plugin %s has marked feed to be ran again after execution has completed.' % self.current_plugin)

    @useFeedLogging
    def execute(self, disable_phases=None, entries=None):
        """Executes the feed.

        :disable_phases: Disable given phases during execution
        :entries: Entries to be used in execution instead
            of using the input. Disables input phase.
        """

        log.debug('executing %s' % self.name)

        self._reset()
        # Handle keyword args
        if disable_phases:
            map(self.disable_phase, disable_phases)
        if entries:
            # If entries are passed for this execution, disable the input phase
            self.disable_phase('input')
            self.entries.extend(entries)

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
            # run phases
            for phase in feed_phases:
                if phase in self.disabled_phases:
                    # log keywords not executed
                    for plugin in self.plugins(phase):
                        if plugin.name in self.config:
                            log.info('Plugin %s is not executed because %s phase is disabled' %
                                     (plugin.name, phase))
                    continue

                # run all plugins with this phase
                self.__run_feed_phase(phase)

                # if abort flag has been set feed should be aborted now
                # since this calls return rerun will not be done
                if self._abort:
                    return

            log.debug('committing session, abort=%s' % self._abort)
            self.session.commit()
            fire_event('feed.execute.completed', self)
        finally:
            # this will cause database rollback on exception and feed.abort
            self.session.close()

        # rerun feed
        if self._rerun:
            if self._rerun_count >= self.max_reruns:
                log.info('Feed has been rerunning already %s times, stopping for now' % self._rerun_count)
                # reset the counter for future runs (neccessary only with webui)
                self._rerun_count = 0
            else:
                log.info('Rerunning the feed')
                self._rerun_count += 1
                self.execute(disable_phases=disable_phases, entries=entries)

    def process_start(self):
        """Execute process_start phase"""
        self.__run_feed_phase('process_start')

    def process_end(self):
        """Execute terminate phase for this feed"""
        if self.manager.options.validate:
            log.debug('No process_end phase with --check')
            return
        self.__run_feed_phase('process_end')

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
