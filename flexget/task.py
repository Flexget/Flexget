import collections.abc
import contextlib
import copy
import itertools
import random
import string
import threading
from functools import total_ordering, wraps
from typing import TYPE_CHECKING, Iterable, List, Optional, Union

from loguru import logger
from sqlalchemy import Column, Integer, String, Unicode

from flexget import config_schema, db_schema
from flexget.db_schema import VersionedBaseMeta
from flexget.entry import Entry, EntryState, EntryUnicodeError
from flexget.event import event, fire_event
from flexget.manager import Session
from flexget.plugin import (
    DependencyError,
    PluginError,
    PluginWarning,
    get_plugins,
    phase_methods,
    plugin_schemas,
    task_phases,
)
from flexget.plugin import plugins as all_plugins
from flexget.terminal import capture_console
from flexget.utils import requests
from flexget.utils.database import with_session
from flexget.utils.simple_persistence import SimpleTaskPersistence
from flexget.utils.sqlalchemy_utils import ContextSession
from flexget.utils.template import FlexGetTemplate, render_from_task
from flexget.utils.tools import MergeException, get_config_hash, merge_dict_from_to

logger = logger.bind(name='task')

if TYPE_CHECKING:
    Base = VersionedBaseMeta
else:
    Base = db_schema.versioned_base('feed', 0)


class TaskConfigHash(Base):
    """Stores the config hash for tasks so that we can tell if the config has changed since last run."""

    __tablename__ = 'feed_config_hash'

    id = Column(Integer, primary_key=True)
    task = Column('name', Unicode, index=True, nullable=False)
    hash = Column('hash', String)

    def __repr__(self) -> str:
        return f'<TaskConfigHash(task={self.task},hash={self.hash})>'


@with_session
def config_changed(task: str = None, session: ContextSession = None) -> None:
    """
    Forces config_modified flag to come out true on next run of `task`. Used when the db changes, and all
    entries need to be reprocessed.

    .. WARNING: DO NOT (FURTHER) USE FROM PLUGINS

    :param task: Name of the task. If `None`, will be set for all tasks.
    :param session: sqlalchemy Session instance
    """
    logger.debug('Marking config for {} as changed.', (task or 'all tasks'))
    task_hash = session.query(TaskConfigHash)
    if task:
        task_hash = task_hash.filter(TaskConfigHash.task == task)
    task_hash.delete()


def use_task_logging(func):
    @wraps(func)
    def wrapper(self, *args, **kw):
        # Set the appropriate logger context while running task
        cms = [logger.contextualize(task=self.name, task_id=self.id, session_id=self.session_id)]
        # Capture console output if configured to do so
        if self.output:
            cms.append(capture_console(self.output))
        with contextlib.ExitStack() as stack:
            for cm in cms:
                stack.enter_context(cm)
            return func(self, *args, **kw)

    return wrapper


class EntryIterator:
    """An iterator over a subset of entries to emulate old task.accepted/rejected/failed/entries properties."""

    def __init__(self, entries: List[Entry], states: Union[EntryState, Iterable[EntryState]]):
        self.all_entries = entries
        if isinstance(states, EntryState):
            states = [states]
        self.filter = lambda e: e._state in states

    def __iter__(self) -> Iterable[Entry]:
        return filter(self.filter, self.all_entries)

    def __bool__(self):
        return any(e for e in self)

    def __len__(self):
        return sum(1 for _e in self)

    def __add__(self, other):
        return itertools.chain(self, other)

    def __radd__(self, other):
        return itertools.chain(other, self)

    def __getitem__(self, item) -> Union[Entry, Iterable[Entry]]:
        if isinstance(item, slice):
            return list(itertools.islice(self, item.start, item.stop))
        if not isinstance(item, int):
            raise ValueError('Index must be integer.')
        for index, entry in enumerate(self):
            if index == item:
                return entry
        else:
            raise IndexError(f'{item} is out of bounds')

    def reverse(self):
        self.all_entries.sort(reverse=True)

    def sort(self, *args, **kwargs):
        self.all_entries.sort(*args, **kwargs)


class EntryContainer(list):
    """Container for a list of entries, also contains accepted, rejected failed iterators over them."""

    def __init__(self, iterable: list = None):
        list.__init__(self, iterable or [])

        self._entries = EntryIterator(self, [EntryState.UNDECIDED, EntryState.ACCEPTED])
        self._accepted = EntryIterator(
            self, EntryState.ACCEPTED
        )  # accepted entries, can still be rejected
        self._rejected = EntryIterator(
            self, EntryState.REJECTED
        )  # rejected entries, can not be accepted
        self._failed = EntryIterator(self, EntryState.FAILED)  # failed entries
        self._undecided = EntryIterator(self, EntryState.UNDECIDED)  # undecided entries (default)

    # Make these read-only properties
    entries: EntryIterator = property(lambda self: self._entries)
    accepted: EntryIterator = property(lambda self: self._accepted)
    rejected: EntryIterator = property(lambda self: self._rejected)
    failed: EntryIterator = property(lambda self: self._failed)
    undecided: EntryIterator = property(lambda self: self._undecided)

    def __repr__(self) -> str:
        return f'<EntryContainer({list.__repr__(self)})>'


class TaskAbort(Exception):
    def __init__(self, reason: str, silent: bool = False) -> None:
        self.reason = reason
        self.silent = silent

    def __repr__(self):
        return f'TaskAbort(reason={self.reason}, silent={self.silent})'


@total_ordering
class Task:
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

    # Used to determine task order, when priority is the same
    _counter = itertools.count()

    RERUN_DEFAULT = 5
    RERUN_MAX = 100

    def __init__(
        self,
        manager,
        name,
        config=None,
        options=None,
        output=None,
        session_id=None,
        priority=None,
        suppress_warnings=None,
    ):
        """
        :param Manager manager: Manager instance.
        :param string name: Name of the task.
        :param dict config: Task configuration.
        :param options: dict or argparse namespace with options for this task
        :param output: A filelike that all console output will be sent to for this task.
        :param session_id: Session id that will be attached to all log messages for filtering
        :param priority: If multiple tasks are waiting to run, the task with the lowest priority will be run first.
            The default is 0, if the cron option is set though, the default is lowered to 10.
        :param suppress_warnings: Allows suppressing log warning about missing plugin in key phases

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
        # If execution hasn't specifically set the `allow_manual` flag, set it to False by default
        if not hasattr(options, 'allow_manual'):
            options.allow_manual = False
        self.options = options
        self.output = output
        self.session_id = session_id
        self.suppress_warnings = suppress_warnings or []
        if priority is None:
            self.priority = 10 if self.options.cron else 0
        else:
            self.priority = priority
        self.priority = priority
        self._count = next(self._counter)
        self.finished_event = threading.Event()

        # simple persistence
        self.simple_persistence = SimpleTaskPersistence(self)

        # rerun related flags and values
        self._rerun_count = 0
        self._max_reruns = Task.RERUN_DEFAULT
        self._reruns_locked = False

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
        self.disabled_plugins = []

        # current state
        self.current_phase = None
        self.current_plugin = None
        self.traceback: Optional[str] = None

    @property
    def max_reruns(self):
        """How many times task can be rerunned before stopping"""
        return self._max_reruns

    @max_reruns.setter
    def max_reruns(self, value):
        """Set new maximum value for reruns unless property has been locked"""
        if not self._reruns_locked:
            self._max_reruns = value
        else:
            logger.debug('max_reruns is locked, {} tried to modify it', self.current_plugin)

    def lock_reruns(self):
        """Prevent modification of max_reruns property"""
        logger.debug('Enabling rerun lock')
        self._reruns_locked = True

    def unlock_reruns(self):
        """Allow modification of max_reruns property"""
        logger.debug('Releasing rerun lock')
        self._reruns_locked = False

    @property
    def reruns_locked(self):
        return self._reruns_locked

    @property
    def is_rerun(self):
        return bool(self._rerun_count)

    @property
    def rerun_count(self):
        return self._rerun_count

    @property
    def undecided(self):
        """
        .. deprecated:: Use API v3

        .. note:: We did not migrate to v3

            If I remember correctly the idea was to make v3 signature
            on_task_xxx(task, config, entries)

            Param entries would be EntryContainer, which has convenience
            iterator methods:

            - entries.accepted
            - entries.failed
            - etc, which you see here
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

    def __lt__(self, other):
        return (self.priority, self._count) < (other.priority, other._count)

    def __eq__(self, other):
        return (self.priority, self._count) == (other.priority, other._count)

    def __str__(self):
        return f'<Task(name={self.name},aborted={self.aborted})>'

    def disable_phase(self, phase):
        """Disable ``phase`` from execution.

        :param string phase: Name of ``phase``
        :raises ValueError: *phase* could not be found.
        """
        if phase not in task_phases:
            raise ValueError('%s is not a valid phase' % phase)
        if phase not in self.disabled_phases:
            logger.debug('Disabling {} phase', phase)
            self.disabled_phases.append(phase)

    def disable_plugin(self, plugin):
        """Disable ``plugin`` from execution.

        :param string plugin: Name of ``plugin``
        :raises ValueError: *plugin* could not be found.
        """
        if plugin not in all_plugins:
            raise ValueError(f'`{plugin}` is not a valid plugin.')
        self.disabled_plugins.append(plugin)

    def abort(self, reason='Unknown', silent=False, traceback: str = None):
        """Abort this task execution, no more plugins will be executed except the abort handling ones."""
        self.aborted = True
        self.abort_reason = reason
        self.silent_abort = silent
        self.traceback = traceback
        if not self.silent_abort:
            logger.warning('Aborting task (plugin: {})', self.current_plugin)
        else:
            logger.debug('Aborting task (plugin: {})', self.current_plugin)
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
            plugins = sorted(
                get_plugins(phase=phase), key=lambda p: p.phase_handlers[phase], reverse=True
            )
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
                    if phase not in self.suppress_warnings:
                        if phase == 'filter':
                            logger.warning(
                                'Task does not have any filter plugins to accept entries. '
                                'You need at least one to accept the entries you want.'
                            )
                        else:
                            logger.warning(
                                'Task doesn\'t have any {} plugins, you should add (at least) one!',
                                phase,
                            )

        for plugin in self.plugins(phase):
            # Abort this phase if one of the plugins disables it
            if phase in self.disabled_phases:
                return
            if plugin.name in self.disabled_plugins:
                continue
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
                            self.all_entries.append(e)
                finally:
                    fire_event('task.execute.after_plugin', self, plugin.name)
                self.session = None
        # check config hash for changes at the end of 'prepare' phase
        if phase == 'prepare':
            self.check_config_hash()

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
            result = method(*args, **kwargs)
            # We exhaust any iterator inputs here to make sure we catch exceptions properly.
            if isinstance(result, collections.abc.Iterable):
                result = list(result)
            return result
        except TaskAbort:
            raise
        except PluginWarning as warn:
            # check if this warning should be logged only once (may keep repeating)
            if warn.kwargs.get('log_once', False):
                from flexget.utils.log import log_once

                log_once(warn.value, warn.logger)
            else:
                warn.logger.warning(warn)
        except EntryUnicodeError as eue:
            msg = 'Plugin {} tried to create non-unicode compatible entry (key: {}, value: {!r})'.format(
                keyword,
                eue.key,
                eue.value,
            )
            logger.critical(msg)
            self.abort(msg)
        except PluginError as err:
            err.logger.critical(err.value)
            self.abort(err.value)
        except DependencyError as e:
            msg = 'Plugin `{}` cannot be used because dependency `{}` is missing.'.format(
                keyword,
                e.missing,
            )
            logger.critical(e.message)
            self.abort(msg)
        except Warning as e:
            # If warnings have been elevated to errors
            msg = f'Warning during plugin {keyword}: {e}'
            logger.exception(msg)
            self.abort(msg)
        except Exception as e:
            msg = f'BUG: Unhandled error in plugin {keyword}: {e}'
            logger.opt(exception=True).critical(msg)
            traceback = self.manager.crash_report()
            self.abort(msg, traceback=traceback)

    def rerun(self, plugin=None, reason=None):
        """
        Immediately re-run the task after execute has completed,
        task can be re-run up to :attr:`.max_reruns` times.

        :param str plugin: Plugin name
        :param str reason: Why the rerun is done
        """
        msg = 'Plugin {} has requested task to be ran again after execution has completed.'.format(
            self.current_plugin if plugin is None else plugin
        )
        if reason:
            msg += f' Reason: {reason}'
        # Only print the first request for a rerun to the info log
        if self._rerun:
            logger.debug(msg)
        else:
            logger.info(msg)
        self._rerun = True

    def config_changed(self):
        """
        Sets config_modified flag to True for the remainder of this run.
        Used when the db changes, and all entries need to be reprocessed.
        """
        self.config_modified = True

    def merge_config(self, new_config):
        try:
            merge_dict_from_to(new_config, self.config)
        except MergeException as e:
            raise PluginError(f'Failed to merge configs for task {self.name}: {e}')

    def check_config_hash(self):
        """
        Checks the task's config hash and updates the hash if necessary.
        """
        # Save current config hash and set config_modified flag
        config_hash = get_config_hash(self.config)
        if self.is_rerun:
            # Restore the config to state right after start phase
            if self.prepared_config:
                self.config = copy.deepcopy(self.prepared_config)
            else:
                logger.error('BUG: No prepared_config on rerun, please report.')
        with Session() as session:
            last_hash = (
                session.query(TaskConfigHash).filter(TaskConfigHash.task == self.name).first()
            )
            if not last_hash:
                session.add(TaskConfigHash(task=self.name, hash=config_hash))
                self.config_changed()
            elif last_hash.hash != config_hash:
                last_hash.hash = config_hash
                self.config_changed()

    def _execute(self):
        """Executes the task without rerunning."""
        if not self.enabled:
            logger.debug('Not running disabled task {}', self.name)
            return

        logger.debug('executing {}', self.name)

        # Handle keyword args
        if self.options.learn:
            logger.info('Disabling download and output phases because of --learn')
            self.disable_phase('download')
            self.disable_phase('output')
        if self.options.disable_phases:
            list(map(self.disable_phase, self.options.disable_phases))
        if self.options.inject:
            # If entries are passed for this execution (eg. rerun), disable the input phase
            self.disable_phase('input')
            self.all_entries.extend(copy.deepcopy(self.options.inject))

        # run phases
        try:
            for phase in task_phases:
                if phase in self.disabled_phases:
                    # log keywords not executed
                    if phase not in self.suppress_warnings:
                        for plugin in self.plugins(phase):
                            if plugin.name in self.config:
                                logger.info(
                                    'Plugin {} is not executed in {} phase because the phase is disabled '
                                    '(e.g. --test, --inject)',
                                    plugin.name,
                                    phase,
                                )
                    continue
                if phase in ('start', 'prepare') and self.is_rerun:
                    logger.debug('skipping phase {} during rerun', phase)
                    continue
                if phase == 'exit':
                    # Make sure we run the entry complete hook before exit phase. These hooks may call for a rerun,
                    # which would mean we should skip the exit phase during this run.
                    for entry in self.all_entries:
                        entry.complete()
                    if self._rerun and self._rerun_count < self.max_reruns:
                        logger.debug('not running task_exit yet because task will rerun')
                        continue
                # run all plugins with this phase
                self.__run_task_phase(phase)
                if phase == 'start':
                    # Store a copy of the config state after start phase to restore for reruns
                    self.prepared_config = copy.deepcopy(self.config)
        except TaskAbort:
            try:
                self.__run_task_phase('abort')
            except TaskAbort as e:
                logger.exception('abort handlers aborted: {}', e)
            raise

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

        self.finished_event.clear()
        try:
            if self.options.cron:
                self.manager.db_cleanup()
            fire_event('task.execute.started', self)
            while True:
                self._execute()
                # rerun task
                if (
                    self._rerun
                    and self._rerun_count < self.max_reruns
                    and self._rerun_count < Task.RERUN_MAX
                ):
                    logger.info('Rerunning the task in case better resolution can be achieved.')
                    self._rerun_count += 1
                    self._all_entries = EntryContainer()
                    self._rerun = False
                    continue
                elif self._rerun:
                    logger.info(
                        'Task has been re-run {} times already, stopping for now',
                        self._rerun_count,
                    )
                break
            fire_event('task.execute.completed', self)
        finally:
            self.finished_event.set()
            self.requests.close()

    @staticmethod
    def validate_config(config):
        schema = plugin_schemas(interface='task')
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

    def render(self, template):
        """
        Renders a template string based on fields in the entry.

        :param template: A template string or FlexGetTemplate that uses jinja2 or python string replacement format.
        :return: The result of the rendering.
        :rtype: string
        :raises RenderError: If there is a problem.
        """
        if not isinstance(template, (str, FlexGetTemplate)):
            raise ValueError(
                'Trying to render non string template or unrecognized template format, got %s'
                % repr(template)
            )
        logger.trace('rendering: {}', template)
        return render_from_task(template, self)


@event('config.register')
def register_config_key():
    task_config_schema = {
        'type': 'object',
        'additionalProperties': plugin_schemas(interface='task'),
    }

    config_schema.register_config_key('tasks', task_config_schema, required=True)
