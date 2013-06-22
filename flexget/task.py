from __future__ import unicode_literals, division, absolute_import
import logging
import copy
import hashlib
from functools import wraps
import itertools

from sqlalchemy import Column, Unicode, String, Integer

from flexget import config_schema
from flexget import db_schema
from flexget.manager import Session, register_config_key
from flexget.plugin import (get_plugins_by_phase, task_phases, PluginWarning, PluginError,
                            DependencyError, plugins as all_plugins, plugin_schemas)
from flexget.utils.simple_persistence import SimpleTaskPersistence
from flexget.event import fire_event
from flexget.entry import EntryUnicodeError
import flexget.utils.requests as requests

log = logging.getLogger('task')
Base = db_schema.versioned_base('feed', 0)


class TaskConfigHash(Base):
    """Stores the config hash for tasks so that we can tell if the config has changed since last run."""

    __tablename__ = 'feed_config_hash'

    id = Column(Integer, primary_key=True)
    task = Column('name', Unicode, index=True, nullable=False)
    hash = Column('hash', String)

    def __repr__(self):
        return '<TaskConfigHash(task=%s,hash=%s)>' % (self.task, self.hash)


def useTaskLogging(func):

    @wraps(func)
    def wrapper(self, *args, **kw):
        # Set the task name in the logger
        from flexget import logger
        logger.set_task(self.name)
        try:
            return func(self, *args, **kw)
        finally:
            logger.set_task('')

    return wrapper


class EntryIterator(object):
    """An iterator over a subset of entries to emulate old task.accepted/rejected/failed/entries properties."""

    def __init__(self, entries, states):
        self.all_entries = entries
        if isinstance(states, basestring):
            states = [states]
        self.filter = lambda e: e._state in states

    def __iter__(self):
        return itertools.ifilter(self.filter, self.all_entries)

    def __bool__(self):
        return any(e for e in self)

    def __len__(self):
        return sum(1 for e in self)

    def __add__(self, other):
        return itertools.chain(self, other)

    def __radd__(self, other):
        return itertools.chain(other, self)

    def __getitem__(self, item):
        if not isinstance(item, int):
            raise ValueError('Index must be integer.')
        for index, entry in enumerate(self):
            if index == item:
                return entry
        else:
            raise IndexError('%d is out of bounds' % item)

    def __getslice__(self, a, b):
        return list(itertools.islice(self, a, b))

    def reverse(self):
        self.all_entries.sort(reverse=True)

    def sort(self, *args, **kwargs):
        self.all_entries.sort(*args, **kwargs)


class EntryContainer(list):
    """Container for a list of entries, also contains accepted, rejected failed iterators over them."""

    def __init__(self, iterable=None):
        list.__init__(self, iterable or [])

        self._entries = EntryIterator(self, ['undecided', 'accepted'])
        self._accepted = EntryIterator(self, 'accepted')  # accepted entries, can still be rejected
        self._rejected = EntryIterator(self, 'rejected')  # rejected entries, can not be accepted
        self._failed = EntryIterator(self, 'failed')  # failed entries
        self._undecided = EntryIterator(self, 'undecided')  # undecided entries (default)

    # Make these read-only properties
    entries = property(lambda self: self._entries)
    accepted = property(lambda self: self._accepted)
    rejected = property(lambda self: self._rejected)
    failed = property(lambda self: self._failed)
    undecided = property(lambda self: self._undecided)

    def __repr__(self):
        return '<EntryContainer(%s)>' % list.__repr__(self)


class Task(object):

    """
    Represents one task in the configuration.

    **Fires events:**

    * task.execute.before_plugin

      Before a plugin is about to be executed. Note that since this will also include all
      builtin plugins the amount of calls can be quite high

      ``parameters: task, keyword``

    * task.execute.after_plugin

      After a plugin has been executed.

      ``parameters: task, keyword``

    * task.execute.completed

      After task execution has been completed

      ``parameters: task``

    """

    max_reruns = 5

    def __init__(self, manager, name, config):
        """
        :param Manager manager: Manager instance.
        :param string name: Name of the task.
        :param dict config: Task configuration.
        """
        self.name = unicode(name)
        self.config = config
        self.manager = manager

        # simple persistence
        self.simple_persistence = SimpleTaskPersistence(self)

        # not to be reset
        self._rerun_count = 0

        # This should not be used until after process_start, when it is evaluated
        self.config_modified = None

        # use reset to init variables when creating
        self._reset()

    # Make these read-only properties
    all_entries = property(lambda self: self._all_entries)
    entries = property(lambda self: self.all_entries.entries)
    accepted = property(lambda self: self.all_entries.accepted)
    rejected = property(lambda self: self.all_entries.rejected)
    failed = property(lambda self: self.all_entries.failed)
    undecided = property(lambda self: self.all_entries.undecided)

    @property
    def is_rerun(self):
        return self._rerun_count

    def _reset(self):
        """Reset task state"""
        log.debug('resetting %s' % self.name)
        self.enabled = True
        self.session = None
        self.priority = 65535

        self.requests = requests.Session()

        # List of all entries in the task
        self._all_entries = EntryContainer()

        self.disabled_phases = []

        # TODO: task.abort() should be done by using exception? not a flag that has to be checked everywhere
        self._abort = False
        self._abort_reason = None
        self._silent_abort = False

        self._rerun = False

        # current state
        self.current_phase = None
        self.current_plugin = None

    def __cmp__(self, other):
        return cmp(self.priority, other.priority)

    def __str__(self):
        return '<Task(name=%s,aborted=%s)>' % (self.name, str(self.aborted))

    @property
    def aborted(self):
        return self._abort and not self._silent_abort

    @property
    def abort_reason(self):
        return self._abort_reason

    def disable_phase(self, phase):
        """Disable ``phase`` from execution.

        All disabled phases are re-enabled by :meth:`Task._reset()` after task
        execution has been completed.

        :param string phase: Name of ``phase``
        :raises ValueError: *phase* could not be found.
        """
        if phase not in task_phases:
            raise ValueError('%s is not a valid phase' % phase)
        if phase not in self.disabled_phases:
            log.debug('Disabling %s phase' % phase)
            self.disabled_phases.append(phase)

    def abort(self, reason='Unknown', **kwargs):
        """Abort this task execution, no more plugins will be executed after the current one exists."""
        if self._abort:
            return
        self._abort_reason = reason
        if not kwargs.get('silent', False):
            log.info('Aborting task (plugin: %s)' % self.current_plugin)
            self._silent_abort = False
        else:
            log.debug('Aborting task (plugin: %s)' % self.current_plugin)
            self._silent_abort = True
        # Run the abort phase before we set the _abort flag
        self._abort = True
        self.__run_task_phase('abort')

    def find_entry(self, category='entries', **values):
        """
        Find and return :class:`~flexget.entry.Entry` with given attributes from task or None

        :param string category: entries, accepted, rejected or failed. Defaults to entries.
        :param values: Key values of entries to be searched
        :return: Entry or None
        """
        cat = getattr(self, category)
        if not isinstance(cat, EntryIterator):
            raise TypeError('category must be a EntryIterator')
        for entry in cat:
            for k, v in values.iteritems():
                if not (k in entry and entry[k] == v):
                    break
            else:
                return entry
        return None

    def plugins(self, phase=None):
        """Get currently enabled plugins.

        :param string phase:
          Optional, limits to plugins currently configured on given phase, sorted in phase order.
        :return:
          An iterator over configured :class:`flexget.plugin.PluginInfo` instances enabled on this task.
        """
        if phase:
            plugins = sorted(get_plugins_by_phase(phase), key=lambda p: p.phase_handlers[phase], reverse=True)
        else:
            plugins = all_plugins.itervalues()
        return (p for p in plugins if p.name in self.config or p.builtin)

    def __run_task_phase(self, phase):
        """Executes task phase, ie. call all enabled plugins on the task.

        Fires events:

        * task.execute.before_plugin
        * task.execute.after_plugin

        :param string phase: Name of the phase
        """
        if phase not in task_phases + ['abort', 'process_start', 'process_end']:
            raise Exception('%s is not a valid task phase' % phase)
        # warn if no inputs, filters or outputs in the task
        if phase in ['input', 'filter', 'output']:
            if not self.manager.unit_test:
                # Check that there is at least one manually configured plugin for these phases
                for p in self.plugins(phase):
                    if not p.builtin:
                        break
                else:
                    log.warning('Task doesn\'t have any %s plugins, you should add (at least) one!' % phase)

        for plugin in self.plugins(phase):
            # Abort this phase if one of the plugins disables it
            if phase in self.disabled_phases:
                return
            # store execute info, except during entry events
            self.current_phase = phase
            self.current_plugin = plugin.name

            if plugin.api_ver == 1:
                # backwards compatibility
                # pass method only task (old behaviour)
                args = (self,)
            else:
                # pass method task, copy of config (so plugin cannot modify it)
                args = (self, copy.copy(self.config.get(plugin.name)))

            try:
                fire_event('task.execute.before_plugin', self, plugin.name)
                response = self.__run_plugin(plugin, phase, args)
                if phase == 'input' and response:
                    # add entries returned by input to self.all_entries
                    for e in response:
                        e.task = self
                    self.all_entries.extend(response)
            finally:
                fire_event('task.execute.after_plugin', self, plugin.name)

            # Make sure we abort if any plugin sets our abort flag
            if self._abort and phase != 'abort':
                return

    def _run_entry_phase(self, phase, entry, **kwargs):
        # TODO: entry events are not very elegant, refactor into real (new) events or something ...
        if phase not in ['accept', 'reject', 'fail']:
            raise Exception('Not a valid entry phase')
        phase_plugins = self.plugins(phase)
        for plugin in phase_plugins:
            self.__run_plugin(plugin, phase, (self, entry), kwargs)

    def __run_plugin(self, plugin, phase, args=None, kwargs=None):
        """
        Execute given plugins phase method, with supplied args and kwargs.
        If plugin throws unexpected exceptions :meth:`abort` will be called.

        :param PluginInfo plugin: Plugin to be executed
        :param string phase: Name of the phase to be executed
        :param args: Passed to the plugin
        :param kwargs: Passed to the plugin
        """
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
        except PluginWarning as warn:
            # check if this warning should be logged only once (may keep repeating)
            if warn.kwargs.get('log_once', False):
                from flexget.utils.log import log_once
                log_once(warn.value, warn.log)
            else:
                warn.log.warning(warn)
        except EntryUnicodeError as eue:
            msg = ('Plugin %s tried to create non-unicode compatible entry (key: %s, value: %r)' %
                   (keyword, eue.key, eue.value))
            log.critical(msg)
            self.abort(msg)
        except PluginError as err:
            err.log.critical(err.value)
            self.abort(err.value)
        except DependencyError as e:
            msg = ('Plugin `%s` cannot be used because dependency `%s` is missing.' %
                   (keyword, e.missing))
            log.critical(msg)
            log.debug(e.message)
            self.abort(msg)
        except Exception as e:
            msg = 'BUG: Unhandled error in plugin %s: %s' % (keyword, e)
            log.exception(msg)
            self.abort(msg)
            # don't handle plugin errors gracefully with unit test
            if self.manager.unit_test:
                raise

    def rerun(self):
        """Immediately re-run the task after execute has completed,
        task can be re-run up to :attr:`.max_reruns` times."""
        if not self._rerun:
            self._rerun = True
            log.info('Plugin %s has requested task to be ran again after execution has completed.' %
                     self.current_plugin)

    def config_changed(self):
        """Forces config_modified flag to come out true on next run. Used when the db changes, and all
        entries need to be reprocessed."""
        log.debug('Marking config as changed.')
        session = self.session or Session()
        task_hash = session.query(TaskConfigHash).filter(TaskConfigHash.task == self.name).first()
        if task_hash:
            task_hash.hash = ''
        self.config_modified = True
        # If we created our own session, commit and close it.
        if not self.session:
            session.commit()
            session.close()

    @useTaskLogging
    def execute(self, disable_phases=None, entries=None):
        """Executes the task.

        :param list disable_phases: Disable given phases names during execution
        :param list entries: Entries to be used in execution instead
            of using the input. Disables input phase.
        """

        log.debug('executing %s' % self.name)

        # Store original config state to be restored if a rerun is needed
        config_backup = copy.deepcopy(self.config)

        self._reset()
        # Handle keyword args
        if disable_phases:
            map(self.disable_phase, disable_phases)
        if entries:
            # If entries are passed for this execution (eg. rerun), disable the input phase
            self.disable_phase('input')
            self.all_entries.extend(entries)

        # validate configuration
        errors = self.validate()
        if self._abort:  # todo: bad practice
            return
        if errors and self.manager.unit_test:  # todo: bad practice
            raise Exception('configuration errors')
        if self.manager.options.validate:
            if not errors:
                log.info('Task \'%s\' passed' % self.name)
            self.enabled = False
            return

        log.debug('starting session')
        self.session = Session()

        # Save current config hash and set config_modidied flag
        config_hash = hashlib.md5(str(sorted(self.config.items()))).hexdigest()
        last_hash = self.session.query(TaskConfigHash).filter(TaskConfigHash.task == self.name).first()
        if self.is_rerun:
            # Make sure on rerun config is not marked as modified
            self.config_modified = False
        elif not last_hash:
            self.config_modified = True
            last_hash = TaskConfigHash(task=self.name, hash=config_hash)
            self.session.add(last_hash)
        elif last_hash.hash != config_hash:
            self.config_modified = True
            last_hash.hash = config_hash
        else:
            self.config_modified = False

        try:
            # run phases
            for phase in task_phases:
                if phase in self.disabled_phases:
                    # log keywords not executed
                    for plugin in self.plugins(phase):
                        if plugin.name in self.config:
                            log.info('Plugin %s is not executed because %s phase is disabled (e.g. --test)' %
                                     (plugin.name, phase))
                    continue

                # run all plugins with this phase
                self.__run_task_phase(phase)

                # if abort flag has been set task should be aborted now
                # since this calls return rerun will not be done
                if self._abort:
                    return

            for entry in self.all_entries:
                entry.complete()
            log.debug('committing session, abort=%s' % self._abort)
            self.session.commit()
            fire_event('task.execute.completed', self)
        finally:
            # this will cause database rollback on exception and task.abort
            self.session.close()

        # rerun task
        if self._rerun:
            if self._rerun_count >= self.max_reruns:
                log.info('Task has been rerunning already %s times, stopping for now' % self._rerun_count)
                # reset the counter for future runs (necessary only with webui)
                self._rerun_count = 0
            else:
                log.info('Rerunning the task in case better resolution can be achieved.')
                self._rerun_count += 1
                # Restore config to original state before running again
                self.config = config_backup
                self.execute(disable_phases=disable_phases, entries=entries)

        # Clean up entries after the task has executed to reduce ram usage, #1652
        if not self.manager.unit_test:
            self.all_entries[:] = [entry for entry in self.all_entries if entry.accepted]

    def _process_start(self):
        """Execute process_start phase"""
        self.__run_task_phase('process_start')

    def _process_end(self):
        """Execute terminate phase for this task"""
        if self.manager.options.validate:
            log.debug('No process_end phase with --check')
            return
        self.__run_task_phase('process_end')

    def validate(self):
        """Called during task execution. Validates config, prints errors and aborts task if invalid."""
        errors = self.validate_config(self.config)
        # log errors and abort
        if errors:
            log.critical('Task \'%s\' has configuration errors:' % self.name)
            msgs = ["[%s] %s" % (e.json_pointer, e.message) for e in errors]
            for msg in msgs:
                log.error(msg)
            # task has errors, abort it
            self.abort('\n'.join(msgs))
        return errors

    @staticmethod
    def validate_config(config):
        schema = plugin_schemas(context='task')
        # Don't validate commented out plugins
        schema['patternProperties'] = {'^_': {}}
        return config_schema.process_config(config, schema)


task_config_schema = {
    'type': 'object',
    'additionalProperties': {'type': 'object'}
}

register_config_key('tasks', task_config_schema, required=True)
# Backwards compatibility with feeds key
register_config_key('feeds', task_config_schema)
