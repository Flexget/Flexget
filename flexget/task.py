from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import copy
import hashlib
import itertools
import logging
import threading
import random
import string
from functools import wraps, total_ordering

from sqlalchemy import Column, Integer, String, Unicode

from flexget import config_schema, db_schema
from flexget.entry import EntryUnicodeError
from flexget.event import event, fire_event
from flexget.logger import capture_output
from flexget.manager import Session
from flexget.plugin import plugins as all_plugins
from flexget.plugin import (
    DependencyError, get_plugins, phase_methods, plugin_schemas, PluginError, PluginWarning, task_phases)
from flexget.utils import requests
from flexget.utils.database import with_session
from flexget.utils.simple_persistence import SimpleTaskPersistence

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


@with_session
def config_changed(task=None, session=None):
    """
    Forces config_modified flag to come out true on next run of `task`. Used when the db changes, and all
    entries need to be reprocessed.

    :param task: Name of the task. If `None`, will be set for all tasks.
    """
    log.debug('Marking config for %s as changed.' % (task or 'all tasks'))
    task_hash = session.query(TaskConfigHash)
    if task:
        task_hash = task_hash.filter(TaskConfigHash.task == task)
    task_hash.delete()


def use_task_logging(func):

    @wraps(func)
    def wrapper(self, *args, **kw):
        # Set the task name in the logger and capture output
        from flexget import logger
        with logger.task_logging(self.name):
            if self.output:
                with capture_output(self.output, loglevel=self.loglevel):
                    return func(self, *args, **kw)
            else:
                return func(self, *args, **kw)

    return wrapper


class EntryIterator(object):
    """An iterator over a subset of entries to emulate old task.accepted/rejected/failed/entries properties."""

    def __init__(self, entries, states):
        self.all_entries = entries
        if isinstance(states, str):
            states = [states]
        self.filter = lambda e: e._state in states

    def __iter__(self):
        return filter(self.filter, self.all_entries)

    def __bool__(self):
        return any(e for e in self)

    def __len__(self):
        return sum(1 for e in self)

    def __add__(self, other):
        return itertools.chain(self, other)

    def __radd__(self, other):
        return itertools.chain(other, self)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self, item.start, item.stop))
        if not isinstance(item, int):
            raise ValueError('Index must be integer.')
        for index, entry in enumerate(self):
            if index == item:
                return entry
        else:
            raise IndexError('%d is out of bounds' % item)

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


class TaskAbort(Exception):
    def __init__(self, reason, silent=False):
        self.reason = reason
        self.silent = silent

    def __repr__(self):
        return 'TaskAbort(reason=%s, silent=%s)' % (self.reason, self.silent)


@total_ordering
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

    * task.execute.started

      Before a task starts execution

    * task.execute.completed

      After task execution has been completed

      ``parameters: task``

    """

    max_reruns = 5
    # Used to determine task order, when priority is the same
    _counter = itertools.count()

    def __init__(self, manager, name, config=None, options=None, output=None, loglevel=None, priority=None):
        """
        :param Manager manager: Manager instance.
        :param string name: Name of the task.
        :param dict config: Task configuration.
        :param options: dict or argparse namespace with options for this task
        :param output: A filelike that all logs and stdout will be sent to for this task.
        :param loglevel: Custom loglevel, only log messages at this level will be sent to `output`
        :param priority: If multiple tasks are waiting to run, the task with the lowest priority will be run first.
            The default is 0, if the cron option is set though, the default is lowered to 10.

        """
        self.name = str(name)
        self.id = ''.join(random.choice(string.digits) for _ in range(6))
        self.manager = manager
        if config is None:
            config = manager.config['tasks'].get(name, {})
        self.config = copy.deepcopy(config)
        self.prepared_config = None
        if options is None:
            options = copy.copy(self.manager.options.execute)
        elif isinstance(options, dict):
            options_namespace = copy.copy(self.manager.options.execute)
            options_namespace.__dict__.update(options)
            options = options_namespace
        self.options = options
        self.output = output
        self.loglevel = loglevel
        if priority is None:
            self.priority = 10 if self.options.cron else 0
        else:
            self.priority = priority
        self.priority = priority
        self._count = next(self._counter)
        self.finished_event = threading.Event()

        # simple persistence
        self.simple_persistence = SimpleTaskPersistence(self)

        # not to be reset
        self._rerun_count = 0

        self.config_modified = None

        self.enabled = not self.name.startswith('_')

        # These are just to query what happened in task. Call task.abort to set.
        self.aborted = False
        self.abort_reason = None
        self.silent_abort = False

        self.session = None

        self.requests = requests.Session()

        # List of all entries in the task
        self._all_entries = EntryContainer()
        self._rerun = False

        self.disabled_phases = []

        # current state
        self.current_phase = None
        self.current_plugin = None

    @property
    def undecided(self):
        """
        .. deprecated:: Use API v3
        """
        return self.all_entries.undecided

    @property
    def failed(self):
        """
        .. deprecated:: Use API v3
        """
        return self.all_entries.failed

    @property
    def rejected(self):
        """
        .. deprecated:: Use API v3
        """
        return self.all_entries.rejected

    @property
    def accepted(self):
        """
        .. deprecated:: Use API v3
        """
        return self.all_entries.accepted

    @property
    def entries(self):
        """
        .. deprecated:: Use API v3
        """
        return self.all_entries.entries

    @property
    def all_entries(self):
        """
        .. deprecated:: Use API v3
        """
        return self._all_entries

    @property
    def is_rerun(self):
        return self._rerun_count

    def __lt__(self, other):
        return (self.priority, self._count) < (other.priority, other._count)

    def __eq__(self, other):
        return (self.priority, self._count) == (other.priority, other._count)

    def __str__(self):
        return '<Task(name=%s,aborted=%s)>' % (self.name, self.aborted)

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

    def abort(self, reason='Unknown', silent=False):
        """Abort this task execution, no more plugins will be executed except the abort handling ones."""
        self.aborted = True
        self.abort_reason = reason
        self.silent_abort = silent
        if not self.silent_abort:
            log.warning('Aborting task (plugin: %s)' % self.current_plugin)
        else:
            log.debug('Aborting task (plugin: %s)' % self.current_plugin)
        raise TaskAbort(reason, silent=silent)

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
            for k, v in values.items():
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
            plugins = sorted(get_plugins(phase=phase), key=lambda p: p.phase_handlers[phase], reverse=True)
        else:
            plugins = iter(all_plugins.values())
        return (p for p in plugins if p.name in self.config or p.builtin)

    def __run_task_phase(self, phase):
        """Executes task phase, ie. call all enabled plugins on the task.

        Fires events:

        * task.execute.before_plugin
        * task.execute.after_plugin

        :param string phase: Name of the phase
        """
        if phase not in phase_methods:
            raise Exception('%s is not a valid task phase' % phase)
        # warn if no inputs, filters or outputs in the task
        if phase in ['input', 'filter', 'output']:
            if not self.manager.unit_test:
                # Check that there is at least one manually configured plugin for these phases
                for p in self.plugins(phase):
                    if not p.builtin:
                        break
                else:
                    if phase == 'filter':
                        log.warning('Task does not have any filter plugins to accept entries. '
                                    'You need at least one to accept the entries you  want.')
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

            # Hack to make task.session only active for a single plugin
            with Session() as session:
                self.session = session
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
                self.session = None

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
        except TaskAbort:
            raise
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
        except Warning as e:
            # If warnings have been elevated to errors
            msg = 'Warning during plugin %s: %s' % (keyword, e)
            log.exception(msg)
            self.abort(msg)
        except Exception as e:
            msg = 'BUG: Unhandled error in plugin %s: %s' % (keyword, e)
            log.critical(msg)
            self.manager.crash_report()
            self.abort(msg)

    def rerun(self):
        """Immediately re-run the task after execute has completed,
        task can be re-run up to :attr:`.max_reruns` times."""
        msg = 'Plugin %s has requested task to be ran again after execution has completed.' % self.current_plugin
        # Only print the first request for a rerun to the info log
        log.debug(msg) if self._rerun else log.info(msg)
        self._rerun = True

    def config_changed(self):
        """
        Sets config_modified flag to True for the remainder of this run.
        Used when the db changes, and all entries need to be reprocessed.
        """
        self.config_modified = True

    def _execute(self):
        """Executes the task without rerunning."""
        if not self.enabled:
            log.debug('Not running disabled task %s' % self.name)
            return

        log.debug('executing %s' % self.name)

        # Handle keyword args
        if self.options.learn:
            log.info('Disabling download and output phases because of --learn')
            self.disable_phase('download')
            self.disable_phase('output')
        if self.options.disable_phases:
            list(map(self.disable_phase, self.options.disable_phases))
        if self.options.inject:
            # If entries are passed for this execution (eg. rerun), disable the input phase
            self.disable_phase('input')
            self.all_entries.extend(self.options.inject)

        # Save current config hash and set config_modidied flag
        with Session() as session:
            task_templates = {}
            templates = self.config.get('template', [])
            for template, value in self.manager.config.get('templates', {}).items():
                if isinstance(templates, basestring) or isinstance(templates, list) and template in templates:
                    task_templates.update({template: value})
            hashable_config = list(self.config.items()) + list(task_templates.items())
            config_hash = hashlib.md5(str(sorted(hashable_config)).encode('utf-8')).hexdigest()
            last_hash = session.query(TaskConfigHash).filter(TaskConfigHash.task == self.name).first()
            if self.is_rerun:
                # Restore the config to state right after start phase
                if self.prepared_config:
                    self.config = copy.deepcopy(self.prepared_config)
                else:
                    log.error('BUG: No prepared_config on rerun, please report.')
                self.config_modified = False
            elif not last_hash:
                self.config_modified = True
                last_hash = TaskConfigHash(task=self.name, hash=config_hash)
                session.add(last_hash)
            elif last_hash.hash != config_hash:
                self.config_modified = True
                last_hash.hash = config_hash
            else:
                self.config_modified = False

        # run phases
        try:
            for phase in task_phases:
                if phase in self.disabled_phases:
                    # log keywords not executed
                    for plugin in self.plugins(phase):
                        if plugin.name in self.config:
                            log.info('Plugin %s is not executed because %s phase is disabled (e.g. --test)' %
                                     (plugin.name, phase))
                    continue
                if phase == 'start' and self.is_rerun:
                    log.debug('skipping task_start during rerun')
                elif phase == 'exit' and self._rerun and self._rerun_count < self.max_reruns:
                    log.debug('not running task_exit yet because task will rerun')
                else:
                    # run all plugins with this phase
                    self.__run_task_phase(phase)
                    if phase == 'start':
                        # Store a copy of the config state after start phase to restore for reruns
                        self.prepared_config = copy.deepcopy(self.config)
        except TaskAbort:
            try:
                self.__run_task_phase('abort')
            except TaskAbort as e:
                log.exception('abort handlers aborted: %s' % e)
            raise
        else:
            for entry in self.all_entries:
                entry.complete()

    @use_task_logging
    def execute(self):
        """
        Executes the the task.

        If :attr:`.enabled` is False task is not executed. Certain :attr:`.options`
        affect how execution is handled.

        - :attr:`.options.disable_phases` is a list of phases that are not enabled
          for this execution.
        - :attr:`.options.inject` is a list of :class:`Entry` instances used instead
          of running input phase.
        """

        try:
            self.finished_event.clear()
            if self.options.cron:
                self.manager.db_cleanup()
            fire_event('task.execute.started', self)
            while True:
                self._execute()
                # rerun task
                if self._rerun and self._rerun_count < self.max_reruns:
                    log.info('Rerunning the task in case better resolution can be achieved.')
                    self._rerun_count += 1
                    # TODO: Potential optimization is to take snapshots (maybe make the ones backlog uses built in
                    # instead of taking another one) after input and just inject the same entries for the rerun
                    self._all_entries = EntryContainer()
                    self._rerun = False
                    continue
                elif self._rerun:
                    log.info('Task has been re-run %s times already, stopping for now' % self._rerun_count)
                break
            fire_event('task.execute.completed', self)
        finally:
            self.finished_event.set()

    @staticmethod
    def validate_config(config):
        schema = plugin_schemas(context='task')
        # Don't validate commented out plugins
        schema['patternProperties'] = {'^_': {}}
        return config_schema.process_config(config, schema)

    def __copy__(self):
        new = type(self)(self.manager, self.name, self.config, self.options)
        # Update all the variables of new instance to match our own
        new.__dict__.update(self.__dict__)
        # Some mutable objects need to be copies
        new.options = copy.copy(self.options)
        new.config = copy.deepcopy(self.config)
        return new

    copy = __copy__


@event('config.register')
def register_config_key():
    task_config_schema = {
        'type': 'object',
        'additionalProperties': plugin_schemas(context='task')
    }

    config_schema.register_config_key('tasks', task_config_schema, required=True)
