from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
import logging
import Queue
import threading

from flexget.config_schema import register_config_key

log = logging.getLogger('scheduler')

UNITS = ['seconds', 'minutes', 'hours', 'days', 'weeks']
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


# TODO: make tests for this, the defaults probably don't work quite right at the moment
yaml_config = {
    'type': 'object',
    'properties': {
        'every': {'type': 'number', 'default': 1},
        'unit': {'type': 'string', 'enum': UNITS, 'default': 'hours'},
        'on_day': {'type': 'string', 'enum': WEEKDAYS},
        'at_time': {'type': 'string', 'format': 'time'}},
    'additionalProperties': False,
    'dependencies': {
        'on_day': {
            'properties': {
                'amount': {'type': 'integer'},
                'unit': {
                    'enum': ['weeks'],
                    'default': 'weeks'}}},
        'at_time': {
            'properties': {
                'amount': {'type': 'integer'},
                'unit': {
                    'enum': ['days', 'weeks'],
                    'default': 'days'}}}}}

# TODO: make a 'schedule' format keyword for this?
text_config = {'type': 'string', 'pattern': '^every '}

main_schema = {
    'properties': {
        'tasks': {'type': 'object', 'additionalProperties': {'oneOf': [text_config, yaml_config]}},
        'default': {'oneOf': [text_config, yaml_config]}
    }
}


class Scheduler(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    periodic_jobs_lock = threading.Lock()

    def __init__(self, manager):
        super(Scheduler, self).__init__()
        self.run_queue = Queue.PriorityQueue()
        self.manager = manager
        self.periodic_jobs = []

    def execute(self, task):
        """Add a task to the scheduler to be run immediately."""
        # Create a copy of task, so that changes to instance in manager thread do not affect scheduler thread
        job = ImmediateJob(task.copy())
        self.run_queue.put(job)

    def add_scheduled_task(self, task, schedule):
        """Add a task to the scheduler to be run periodically on `schedule`."""
        job = PeriodicJob(task.copy(), schedule)
        with self.periodic_jobs_lock:
            self.periodic_jobs.append(job)

    def update_scheduled_task(self, task, schedule=None):
        with self.periodic_jobs_lock:
            for job in self.periodic_jobs:
                if job.task == task:
                    job.task = task.copy()
                    if schedule:
                        job.schedule = schedule
                    break
            else:
                raise ValueError('task %s was not found among scheduled tasks' % task)

    def remove_scheduled_task(self, task):
        with self.periodic_jobs_lock:
            for job in self.periodic_jobs:
                if job.task == task:
                    break
            else:
                raise ValueError('task %s was not found among scheduled tasks' % task)
            self.periodic_jobs.remove(job)

    def queue_pending_jobs(self):
        # Add pending jobs to the run queue
        with self.periodic_jobs_lock:
            for job in self.periodic_jobs:
                if job.should_run:
                    # Make sure it is not added to the queue again until it is done running
                    job.running = True
                    self.run_queue.put(job)

    def run(self):
        while True:
            self.queue_pending_jobs()
            # Grab the first job from the run queue and do it
            try:
                job = self.run_queue.get(timeout=0.5)
            except Queue.Empty:
                continue
            job.start()
            try:
                if job.task is SHUTDOWN:
                    # shutdown job, exit the main loop
                    break
                job.task.execute()
            finally:
                self.run_queue.task_done()
                job.done()
        remaining_jobs = self.run_queue.qsize()
        if remaining_jobs:
            log.warning('Scheduler shut down with %s jobs remaining in the queue to run.' % remaining_jobs)
        log.debug('scheduler shut down')

    def shutdown(self, finish_queue=True):
        """
        Ends the thread. If a job is running, waits for it to finish first.

        :param bool finish_queue: If this is True, shutdown will wait until all queued tasks have finished.
        """
        job = ShutdownJob()
        job.priority = 10 if finish_queue else -1
        self.run_queue.put(job)


class Job(object):
    """A job for the scheduler to execute."""
    #: Used to determine which job to run first when multiple jobs are waiting.
    priority = None
    #: A datetime object when the job was scheduled to run. Jobs are sorted by this value when priority is the same.
    run_time = None
    #: The :class:`Task` this job executes
    task = None

    def start(self):
        """Called when the job is run."""
        pass

    def done(self):
        """Called when the job has finished running."""
        pass

    def __lt__(self, other):
        return (self.priority, self.run_time) < (other.priority, other.run_time)


SHUTDOWN = object()

class ShutdownJob(Job):
    priority = -1
    task = SHUTDOWN


class ImmediateJob(Job):
    priority = 1

    def __init__(self, task):
        self.task = task
        self.run_time = datetime.now()


class PeriodicJob(Job):
    priority = 5
    _schedule_attrs = ['unit', 'amount', 'on_day', 'at_time']

    def __init__(self, task, schedule):
        self.task = task
        self.running = False
        self.execute_options = None
        self.unit = None
        self.amount = None
        self.on_day = None
        self.at_time = None
        self.last_run = None
        self.run_time = None
        self.schedule = schedule

    @property
    def schedule(self):
        schedule = {}
        for key in self._schedule_attrs:
            schedule[key] = getattr(self, key)
        return schedule

    @schedule.setter
    def schedule(self, schedule):
        # Don't apply bad updates
        old_schedule = self.schedule
        try:
            if isinstance(schedule, basestring):
                self._parse_schedule_text(schedule)
            else:
                invalid_keys = [k for k in schedule if k not in self._schedule_attrs]
                if invalid_keys:
                    raise ValueError('the following are not valid keys in a schedule dictionary: %s' % ', '.join(invalid_keys))
                for key in self._schedule_attrs:
                    setattr(self, key, schedule.get(key))
            self._validate()
        except:
            self.schedule = old_schedule
            raise
        self.schedule_next_run()

    def start(self):
        self.running = True
        self.last_run = datetime.now()

    def done(self):
        self.schedule_next_run()
        self.running = False

    def _validate(self):
        """Makes sure schedule is valid."""
        if not self.unit or not self.amount:
            raise ValueError('unit and amount must be specified')
        if self.unit not in UNITS:
            raise ValueError('`%s` is not a valid unit' % self.unit)
        if self.on_day and self.on_day not in WEEKDAYS:
            raise ValueError('`%s` is not a valid day of week' % self.on_day)
        if self.on_day and self.unit != 'weeks':
            raise ValueError('unit must be weeks when on_day is used')
        if self.at_time and self.unit not in ['days', 'weeks']:
            raise ValueError('unit must be days or weeks when at_time is used')
        if self.on_day or self.at_time and int(self.amount) != self.amount:
            raise ValueError('amount must be an integer when on_day or at_time are used')

    @property
    def should_run(self):
        return not self.running and self.run_time and datetime.now() >= self.run_time

    @property
    def period(self):
        return timedelta(**{self.unit: self.amount})

    def schedule_next_run(self):
        last_run = self.last_run
        if not last_run:
            # Pretend we ran one period ago
            last_run = datetime.now() - self.period
        if self.on_day:
            days_ahead = self.on_day - last_run.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            self.run_time = last_run + timedelta(days=days_ahead, weeks=self.amount-1)
        else:
            self.run_time = last_run + self.period
        if self.at_time:
            self.run_time = self.run_time.replace(hour=self.at_time.hour, minute=self.at_time.minute,
                                                  second=self.at_time.second)

    # TODO: Probably remove this, and go with the yaml form defined by above schema
    # format: every NUM UNIT [on WEEKDAY] [at TIME]
    def _parse_schedule_text(self, text):
        result = {}
        word_iter = iter(text.lower().split(' '))
        try:
            if next(word_iter, '') != 'every':
                raise ValueError('schedule string must start with `every`')
            word = next(word_iter, '')
            if word in WEEKDAYS:
                self.unit = 'weeks'
                self.amount = 1
                self.on_day = word
                word = next(word_iter)
            else:
                try:
                    self.amount = float(word)
                    word = next(word_iter, '')
                except ValueError:
                    self.amount = 1
                if word + 's' in UNITS:
                    word += 's'
                if word not in UNITS:
                    raise ValueError('`%s` is not a valid unit' % word)
                self.unit = word
                word = next(word_iter)
                if word == 'on':
                    if self.unit != 'weeks':
                        raise ValueError('`on` may only be specified when the unit is weeks')
                    if int(self.amount) != self.amount:
                        raise ValueError('week quantity must be an integer when `at` is specified')
                    word = next(word_iter, '')
                    try:
                        self.on_day = datetime.strptime(word, '%A').weekday()
                    except ValueError:
                        raise ValueError('`%s` is not a valid weekday' % word)
                    word = next(word_iter)
            if word == 'at':
                if self.unit not in ['days', 'weeks']:
                    raise ValueError('can only specify `at` when unit is days or weeks')
                if int(self.amount) != self.amount:
                    raise ValueError('%s quantity must be an integer when `at` is specified' % self.unit)
                # Try to get the next two words, since this is the last parameter and they might have am/pm
                word = next(word_iter, '') + ' ' + next(word_iter, '')
                # Try parsing with AM/PM first, then 24 hour time
                try:
                    self.at_time = datetime.strptime(word, '%I:%M %p')
                except ValueError:
                    try:
                        self.at_time = datetime.strptime(word, '%H:%M')
                    except ValueError:
                        raise ValueError('invalid time `%s`' % word)
            else:
                raise ValueError('`%s` is unrecognized in the schedule string' % word)
            try:
                word = next(word_iter)
                raise ValueError('`%s` is unrecognized in the schedule string' % word)
            except StopIteration:
                pass
        except StopIteration:
            pass
        return result


register_config_key('schedules', main_schema)
