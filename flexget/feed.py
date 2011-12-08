import logging
import copy
from flexget import validator
from flexget.manager import Session, register_config_key
from flexget.plugin import get_plugins_by_phase, get_plugin_by_name, \
    feed_phases, PluginWarning, PluginError, DependencyError, plugins as all_plugins
from flexget.utils.simple_persistence import SimpleFeedPersistence
from flexget.event import fire_event
from flexget.entry import Entry, EntryUnicodeError

log = logging.getLogger('feed')


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
        """
        Find and return entry with given attributes from feed or None
        :param category: entries, accepted, rejected or failed. Defaults to entries.
        :param values: Key values of entries to be searched
        :return: Entry or None
        """
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

    def plugins(self, phase=None):
        """An iterator over PluginInfo instances enabled on this feed.

        :param phase: Optional, limits to plugins enabled on given phase, sorted in phase order.
        :return: Iterator of PluginInfo instances enabled on this feed.
        """
        if phase:
            plugins = sorted(get_plugins_by_phase(phase), key=lambda p: p.phase_handlers[phase], reverse=True)
        else:
            plugins = all_plugins.itervalues()
        return (p for p in plugins if p.name in self.config or p.builtin)

    def __run_feed_phase(self, phase):
        if phase not in feed_phases + ['abort', 'process_start', 'process_end']:
            raise Exception('%s is not a valid feed phase' % phase)
        # warn if no inputs, filters or outputs in the feed
        if phase in ['input', 'filter', 'output']:
            if not self.manager.unit_test:
                # Check that there is at least one manually configured plugin for these phases
                for p in self.plugins(phase):
                    if not p.builtin:
                        break
                else:
                    log.warning('Feed doesn\'t have any %s plugins, you should add (at least) one!' % phase)

        for plugin in self.plugins(phase):
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
                # pass method feed, copy of config (so plugin cannot modify it)
                args = (self, copy.copy(self.config.get(plugin.name)))

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

        # log.trace('Running %s method %s' % (keyword, method))
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
        """Immediately re-run the feed after execute has completed."""
        self._rerun = True
        log.info('Plugin %s has requested feed to be ran again after execution has completed.' % self.current_plugin)

    @useFeedLogging
    def execute(self, disable_phases=None, entries=None):
        """Executes the feed.

        :param disable_phases: Disable given phases during execution
        :param entries: Entries to be used in execution instead
            of using the input. Disables input phase.
        """

        log.debug('executing %s' % self.name)

        self._reset()
        # Handle keyword args
        if disable_phases:
            map(self.disable_phase, disable_phases)
        if entries:
            # If entries are passed for this execution (eg. rerun), disable the input phase
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
                log.info('Feed \'%s\' passed' % self.name)
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
                # reset the counter for future runs (necessary only with webui)
                self._rerun_count = 0
            else:
                log.info('Rerunning the feed in case better resolution can be achieved.')
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


def root_config_validator():
    """Returns a validator for the 'feeds' key of config."""
    # TODO: better error messages
    valid_plugins = [p for p in all_plugins if hasattr(all_plugins[p].instance, 'validator')]
    root = validator.factory('dict')
    root.reject_keys(valid_plugins, message='plugins should go under a specific feed. '
        '(and feeds are not allowed to be named the same as any plugins)')
    root.accept_any_key('dict').accept_any_key('any')
    return root


register_config_key('feeds', root_config_validator)
