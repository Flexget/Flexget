from __future__ import unicode_literals, division, absolute_import
import copy
from datetime import datetime, timedelta, time as dt_time
import fnmatch
from hashlib import md5
import logging
import Queue
import threading
import time

from sqlalchemy import Column, String, DateTime

from flexget.config_schema import register_config_key, parse_time
from flexget.db_schema import versioned_base
from flexget.event import event
from flexget.manager import Session
from flexget.task import Task, TaskAbort

log = logging.getLogger('scheduler')
Base = versioned_base('scheduler', 0)

UNITS = ['seconds', 'minutes', 'hours', 'days', 'weeks']
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


yaml_schedule = {
    'type': 'object',
    'properties': {
        'seconds': {'type': 'number'},
        'minutes': {'type': 'number'},
        'hours': {'type': 'number'},
        'days': {'type': 'number'},
        'weeks': {'type': 'number'},
        'at_time': {'type': 'string', 'format': 'time'},
        'on_day': {'type': 'string', 'enum': WEEKDAYS}
    },
    # Only allow one unit to be specified
    'oneOf': [{'required': [unit]} for unit in UNITS],
    'error_oneOf': 'Interval must be specified as one of %s' % ', '.join(UNITS),
    'dependencies': {
        'at_time': {
            'properties': {'days': {'type': 'integer'}, 'weeks': {'type': 'integer'}},
            'oneOf': [{'required': ['days']}, {'required': ['weeks']}],
            'error': 'Interval must be an integer number of days or weeks when `at_time` is specified.',
        },
        'on_day': {
            'properties': {'weeks': {'type': 'integer'}},
            'required': ['weeks'],
            'error': 'Unit must be an integer number of weeks when `on_day` is specified.'
        }
    },
    'additionalProperties': False
}


main_schema = {
    'type': 'array',
    'items': {
        'properties': {
            'tasks': {'type': ['array', 'string'], 'items': {'type': 'string'}},
            'interval': yaml_schedule
        },
        'required': ['tasks', 'interval'],
        'additionalProperties': False
    }
}


class DBTrigger(Base):
    __tablename__ = 'scheduler_triggers'

    uid = Column(String, primary_key=True)  # Hash of all trigger properties, to uniquely identify the trigger
    last_run = Column(DateTime)

    def __init__(self, uid, last_run=None):
        self.uid = uid
        self.last_run = last_run


@event('manager.config_updated')
def create_triggers(manager):
    manager.scheduler.load_schedules()


class Scheduler(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, manager):
        super(Scheduler, self).__init__(name='scheduler')
        self.daemon = True
        self.run_queue = Queue.PriorityQueue()
        self.manager = manager
        self.triggers = []
        self.run_schedules = True
        self._shutdown_now = False
        self._shutdown_when_finished = False

    def load_schedules(self):
        """Clears current schedules and loads them from the config."""
        with self.triggers_lock:
            self.triggers = []
            if 'schedules' not in self.manager.config:
                log.info('No schedules defined in config. Defaulting to run all tasks on a 1 hour interval.')
            for item in self.manager.config.get('schedules', [{'tasks': ['*'], 'interval': {'hours': 1}}]):
                tasks = item['tasks']
                if not isinstance(tasks, list):
                    tasks = [tasks]
                self.triggers.append(Trigger(item['interval'], tasks, options={'cron': True}))

    def execute(self, options=None, output=None, priority=1, trigger_id=None):
        """
        Add a task to the scheduler to be run immediately.

        :param options: Either an :class:`argparse.Namespace` instance, or a dict, containing options for execution
        :param output: If a file-like object is specified here, log messages and stdout from the execution will be
            written to it.
        :param priority: If there are other executions waiting to be run, they will be run in priority order,
            lowest first.
        :param trigger_id: If a trigger_id is specified, it will be attached to the :class:`Job` instance added to the
            run queue. Used to check that triggers are not fired faster than they can be executed.
        :returns: a list of :class:`threading.Event` instances which will be
            set when each respective task has finished running
        """
        if options is None:
            options = copy.copy(self.manager.options.execute)
        elif isinstance(options, dict):
            options_namespace = copy.copy(self.manager.options.execute)
            options_namespace.__dict__.update(options)
            options = options_namespace
        task_names = self.manager.tasks
        # Handle --tasks
        if options.tasks:
            # Create list of tasks to run, preserving order
            task_names = []
            for arg in options.tasks:
                matches = [t for t in self.manager.tasks if fnmatch.fnmatchcase(unicode(t).lower(), arg.lower())]
                if not matches:
                    log.error('`%s` does not match any tasks' % arg)
                    continue
                task_names.extend(m for m in matches if m not in task_names)
            # Set the option as a list of matching task names so plugins can use it easily
            options.tasks = task_names
        # TODO: 1.2 This is a hack to make task priorities work still, not sure if it's the best one
        task_names = sorted(task_names, key=lambda t: self.manager.config['tasks'][t].get('priority', 65535))

        finished_events = []
        for task_name in task_names:
            task = Task(self.manager, task_name,
                        options=options, output=output, priority=priority, trigger_id=trigger_id)
            self.run_queue.put(task)
            finished_events.append(task.finished_event)
        return finished_events

    def queue_pending_jobs(self):
        # Add pending jobs to the run queue
        with self.triggers_lock:
            for trigger in self.triggers:
                if trigger.should_run:
                    with self.run_queue.mutex:
                        if any(j.trigger_id == trigger.uid for j in self.run_queue.queue):
                            log.error('Not firing schedule %r. Tasks from last run have still not finished.' % trigger)
                            log.error('You may need to increase the interval for this schedule.')
                            continue
                    options = dict(trigger.options)
                    # If the user has specified all tasks with '*', don't add tasks option at all, so that manual
                    # tasks are not executed
                    if trigger.tasks != ['*']:
                        options['tasks'] = trigger.tasks
                    self.execute(options=options, priority=5, trigger_id=trigger.uid)
                    trigger.trigger()

    def start(self, run_schedules=None):
        if run_schedules is not None:
            self.run_schedules = run_schedules
        super(Scheduler, self).start()

    def run(self):
        while not self._shutdown_now:
            if self.run_schedules:
                self.queue_pending_jobs()
            # Grab the first job from the run queue and do it
            try:
                task = self.run_queue.get(timeout=0.5)
            except Queue.Empty:
                if self._shutdown_when_finished:
                    self._shutdown_now = True
                continue
            try:
                task.execute()
            except TaskAbort as e:
                log.debug('task %s aborted: %r' % (task.name, e))
            finally:
                self.run_queue.task_done()
        remaining_jobs = self.run_queue.qsize()
        if remaining_jobs:
            log.warning('Scheduler shut down with %s jobs remaining in the queue to run.' % remaining_jobs)
        log.debug('scheduler shut down')

    def wait(self):
        """
        Waits for the thread to exit.
        Similar to :method:`Thread.join`, except it allows ctrl-c to be caught still.
        """
        while self.is_alive():
            time.sleep(0.1)

    def shutdown(self, finish_queue=True):
        """
        Ends the thread. If a job is running, waits for it to finish first.

        :param bool finish_queue: If this is True, shutdown will wait until all queued tasks have finished.
        """
        if finish_queue:
            self._shutdown_when_finished = True
        else:
            self._shutdown_now = True


class Trigger(object):
    def __init__(self, interval, tasks, options=None):
        """
        :param dict interval: An interval dictionary from the config.
        :param list tasks: List of task names specified to run. Wildcards are allowed.
        :param dict options: Dictionary of options that should be applied to this run.
        """
        self.tasks = tasks
        self.options = options
        self.unit = None
        self.amount = None
        self.on_day = None
        self.at_time = None
        self.last_run = None
        self.run_at = None
        self.interval = interval
        self._get_db_last_run()
        self.schedule_next_run()

    @property
    def uid(self):
        """A unique id which describes this trigger."""
        # Determine uniqueness based on interval,
        hashval = md5(str(sorted(self.interval)))
        # and tasks run on that interval.
        hashval.update(','.join(self.tasks).encode('utf-8'))
        return hashval.hexdigest()

    # Handles getting and setting interval in form validated by config
    @property
    def interval(self):
        interval = {self.unit: self.amount}
        if self.at_time:
            interval['at_time'] = self.at_time
        if self.on_day:
            interval['on_day'] = self.on_day
        return interval

    @interval.setter
    def interval(self, interval):
        if not interval:
            for attr in ['unit', 'amount', 'on_day', 'at_time']:
                setattr(self, attr, None)
            return
        for unit in UNITS:
            self.amount = interval.pop(unit, None)
            if self.amount:
                self.unit = unit
                break
        else:
            raise ValueError('Schedule interval must provide a unit and amount')
        self.at_time = interval.pop('at_time', None)
        if self.at_time and not isinstance(self.at_time, dt_time):
            self.at_time = parse_time(self.at_time)
        self.on_day = interval.pop('on_day', None)
        if interval:
            raise ValueError('the following are not valid keys in a schedule interval dictionary: %s' %
                             ', '.join(interval))
        self.schedule_next_run()

    def trigger(self):
        """Call when trigger is activated. Records current run time and schedules next run."""
        self.last_run = datetime.now()
        self._set_db_last_run()
        self.schedule_next_run()

    @property
    def should_run(self):
        return self.run_at and datetime.now() >= self.run_at

    @property
    def period(self):
        return timedelta(**{self.unit: self.amount})

    def schedule_next_run(self):
        last_run = self.last_run
        if not last_run:
            # Pretend we ran one period ago
            last_run = datetime.now() - self.period
        if self.on_day:
            days_ahead = WEEKDAYS.index(self.on_day) - last_run.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            self.run_at = last_run + timedelta(days=days_ahead, weeks=self.amount-1)
        else:
            self.run_at = last_run + self.period
        if self.at_time:
            self.run_at = self.run_at.replace(hour=self.at_time.hour, minute=self.at_time.minute,
                                              second=self.at_time.second)

    def _get_db_last_run(self):
        session = Session()
        try:
            db_trigger = session.query(DBTrigger).get(self.uid)
            if db_trigger:
                self.last_run = db_trigger.last_run
                log.debug('loaded last_run from the database')
        finally:
            session.close()

    def _set_db_last_run(self):
        session = Session()
        try:
            db_trigger = session.query(DBTrigger).get(self.uid)
            if not db_trigger:
                db_trigger = DBTrigger(self.uid)
                session.add(db_trigger)
            db_trigger.last_run = self.last_run
            session.commit()
        finally:
            session.close()
        log.debug('recorded last_run to the database')

    def __repr__(self):
        return 'Trigger(tasks=%r, amount=%r, unit=%r)' % (self.tasks, self.amount, self.unit)


class BufferQueue(Queue.Queue):
    """Used in place of a file-like object to capture text and access it safely from another thread."""
    # Allow access to the Empty error from here
    Empty = Queue.Empty

    def write(self, line):
        self.put(line)


@event('config.register')
def register_config():
    register_config_key('schedules', main_schema)
