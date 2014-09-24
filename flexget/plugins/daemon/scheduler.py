from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta, time as dt_time
import logging
import threading
import time

from sqlalchemy import Column, DateTime, Integer

from flexget import db_schema
from flexget.config_schema import register_config_key, parse_time
from flexget.event import event
from flexget.manager import Session
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import singleton

log = logging.getLogger('scheduler')
DB_SCHEMA_VER = 1
Base = db_schema.versioned_base('scheduler', DB_SCHEMA_VER)

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
    'oneOf': [
        {
            'type': 'array',
            'items': {
                'properties': {
                    'tasks': {'type': ['array', 'string'], 'items': {'type': 'string'}},
                    'interval': yaml_schedule
                },
                'required': ['tasks', 'interval'],
                'additionalProperties': False
            }
        },
        {'type': 'boolean', 'enum': [False]}
    ]
}


class DBTrigger(Base):
    __tablename__ = 'scheduler_triggers'

    uid = Column(Integer, primary_key=True)  # Hash of all trigger properties, to uniquely identify the trigger
    last_run = Column(DateTime)

    def __init__(self, uid, last_run=None):
        self.uid = uid
        self.last_run = last_run


@db_schema.upgrade('scheduler')
def db_upgrade(ver, session):
    if ver == 0:
        log.info('Recreating scheduler table. All schedules will trigger again after this upgrade.')
        table = table_schema('scheduler_triggers', session)
        table.drop()
        Base.metadata.create_all(bind=session.bind)
    return DB_SCHEMA_VER


@event('manager.daemon.started')
@event('manager.config_updated')
def setup_scheduler(manager):
    """Starts, stops or restarts the scheduler when config changes."""
    if not manager.is_daemon:
        return
    scheduler = Scheduler(manager)
    if scheduler.is_alive():
        scheduler.stop()
    if manager.config.get('schedules', True):
        scheduler.start()


@event('manager.shutdown')
def stop_scheduler(manager):
    if not manager.is_daemon:
        return
    scheduler = Scheduler(manager)
    scheduler.stop()
    scheduler.wait()


@singleton
class Scheduler(object):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, manager):
        self.manager = manager
        self.triggers = []
        self.running_triggers = {}
        self.waiting_triggers = set()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self.is_alive():
            if self._stop.is_set():
                # If the thread was told to stop, wait for it to end before starting a new one
                self.wait()
            else:
                raise RuntimeError('Cannot start again, scheduler is already running.')
        self._stop.clear()
        self._thread = threading.Thread(name='scheduler', target=self.run)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        if self.is_alive():
            log.debug('Stopping scheduler')
            self._stop.set()

    def is_alive(self):
        return self._thread and self._thread.is_alive()

    def wait(self):
        while self.is_alive():
            time.sleep(0.5)

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

    def queue_pending_jobs(self):
        # Add pending jobs to the run queue
        with self.triggers_lock:
            for trigger in self.triggers:
                if trigger.should_run:
                    if trigger in self.running_triggers:
                        if trigger not in self.waiting_triggers:
                            log.error('Not firing schedule %r. Tasks from last run have still not finished.' % trigger)
                            log.error('You may need to increase the interval for this schedule.')
                            self.waiting_triggers.add(trigger)
                        continue
                    options = dict(trigger.options)
                    # If the user has specified all tasks with '*', don't add tasks option at all, so that manual
                    # tasks are not executed
                    if trigger.tasks != ['*']:
                        options['tasks'] = trigger.tasks
                    if trigger in self.waiting_triggers:
                        self.waiting_triggers.remove(trigger)
                    self.running_triggers[trigger] = self.manager.execute(options=options, priority=5)
                    trigger.trigger()

    def run(self):
        log.debug('scheduler started')
        self.load_schedules()
        while not self._stop.wait(5):
            # Event.wait returns None on python 2.6, manually check the flag. #2705
            if self._stop.is_set():
                break
            try:
                for trigger_id, finished_events in self.running_triggers.items():
                    if all(e.is_set() for e in finished_events):
                        del self.running_triggers[trigger_id]
                self.queue_pending_jobs()
            except Exception:
                log.exception('BUG: Unhandled error in scheduler thread.')
                # This is just to prevent spamming if we get in an error loop. Maybe should be different.
                log.error('Attempting to continue running scheduler thread in one minute.')
                time.sleep(60)
                continue
        log.debug('scheduler shut down')


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
            db_trigger = session.query(DBTrigger).get(hash(self))
            if db_trigger:
                self.last_run = db_trigger.last_run
                log.debug('loaded last_run from the database')
        finally:
            session.close()

    def _set_db_last_run(self):
        session = Session()
        try:
            db_trigger = session.query(DBTrigger).get(hash(self))
            if not db_trigger:
                db_trigger = DBTrigger(hash(self))
                session.add(db_trigger)
            db_trigger.last_run = self.last_run
            session.commit()
        finally:
            session.close()
        log.debug('recorded last_run to the database')

    def __hash__(self):
        """A unique id which describes this trigger."""
        return hash(tuple(sorted(self.interval.iteritems())) + tuple(sorted(self.tasks)))

    def __eq__(self, other):
        return (self.interval, self.tasks) == (other.interval, other.tasks)

    def __repr__(self):
        return 'Trigger(tasks=%r, amount=%r, unit=%r)' % (self.tasks, self.amount, self.unit)


@event('config.register')
def register_config():
    register_config_key('schedules', main_schema)
