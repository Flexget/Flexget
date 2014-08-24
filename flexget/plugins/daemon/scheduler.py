from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta, time as dt_time
from hashlib import md5
import logging
import threading
import time

from sqlalchemy import Column, String, DateTime

from flexget.config_schema import register_config_key, parse_time
from flexget.db_schema import versioned_base
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import singleton

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

    uid = Column(String, primary_key=True)  # Hash of all trigger properties, to uniquely identify the trigger
    last_run = Column(DateTime)

    def __init__(self, uid, last_run=None):
        self.uid = uid
        self.last_run = last_run


@event('manager.daemon.started')
@event('manager.config_updated')
def setup_scheduler(manager):
    """Loads the scheduler settings from config and starts/stops the scheduler as appropriate."""
    if not manager.is_daemon:
        return
    scheduler = Scheduler(manager)
    if manager.config.get('schedules', True):
        scheduler.load_schedules()
        if not scheduler.is_alive():
            scheduler.start()
    else:
        if scheduler.is_alive():
            scheduler.stop()


@singleton
class Scheduler(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, manager):
        threading.Thread.__init__(self, name='scheduler')
        self.daemon = True
        self.manager = manager
        self.triggers = []
        self.running_triggers = {}
        self._stop = threading.Event()

    def start(self):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if self._stop.is_set() and not self.is_alive():
            self.__init__(self.manager)
        threading.Thread.start(self)

    def stop(self):
        self._stop.set()

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
                    if trigger.uid in self.running_triggers:
                        log.error('Not firing schedule %r. Tasks from last run have still not finished.' % trigger)
                        log.error('You may need to increase the interval for this schedule.')
                        continue
                    options = dict(trigger.options)
                    # If the user has specified all tasks with '*', don't add tasks option at all, so that manual
                    # tasks are not executed
                    if trigger.tasks != ['*']:
                        options['tasks'] = trigger.tasks
                    self.running_triggers[trigger.uid] = self.manager.execute(options=options, priority=5)
                    trigger.trigger()

    def run(self):
        log.debug('scheduler started')
        while not self._stop.wait(5):
            for trigger_id, finished_events in self.running_triggers.items():
                if all(e.is_set() for e in finished_events):
                    del self.running_triggers[trigger_id]
            self.queue_pending_jobs()
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


@event('config.register')
def register_config():
    register_config_key('schedules', main_schema)
