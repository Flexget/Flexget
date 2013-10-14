from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta, time as dt_time
import logging
import Queue
import threading
import time
import sys

from flexget.config_schema import register_config_key, parse_time
from flexget.event import event
from flexget.logger import FlexGetFormatter

log = logging.getLogger('scheduler')

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
            'tasks': {'type': 'array', 'items': {'type': 'string'}},
            'interval': yaml_schedule
        },
        'required': ['tasks', 'interval'],
        'additionalProperties': False
    }
}


class Scheduler(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, manager):
        super(Scheduler, self).__init__(name='scheduler')
        self.daemon = True
        self.run_queue = Queue.PriorityQueue()
        self.manager = manager
        self.triggers = []
        self._shutdown_now = False
        self._shutdown_when_finished = False

    def load_schedules(self):
        """Clears current schedules and loads them from the config."""
        with self.triggers_lock:
            self.triggers = []
            for item in self.manager.config.get('schedules', []):
                self.triggers.append(Trigger(item['interval'], item['tasks'], options={'cron': True}))

    def execute(self, task, options=None, output=None):
        """Add a task to the scheduler to be run immediately."""
        # Create a copy of task, so that changes to instance in manager thread do not affect scheduler thread
        job = Job(task, options=options, output=output)
        self.run_queue.put(job)

    def queue_pending_jobs(self):
        # Add pending jobs to the run queue
        with self.triggers_lock:
            for trigger in self.triggers:
                if trigger.should_run:
                    for task in trigger.tasks:
                        self.run_queue.put(Job(task, trigger.options))
                    trigger.trigger()

    def run(self):
        from flexget.task import Task, TaskAbort
        self.load_schedules()
        while not self._shutdown_now:
            self.queue_pending_jobs()
            # Grab the first job from the run queue and do it
            try:
                job = self.run_queue.get(timeout=0.5)
            except Queue.Empty:
                if self._shutdown_when_finished:
                    self._shutdown_now = True
                continue
            job.start()
            if job.output:
                # Hook up our log and stdout to give back to the requester
                old_stdout, old_stderr = sys.stdout, sys.stderr
                sys.stdout, sys.stderr = Tee(job.output, old_stdout), Tee(job.output, old_stderr)
                # TODO: Use a filter to capture only the logging for this execution?
                streamhandler = logging.StreamHandler(job.output)
                streamhandler.setFormatter(FlexGetFormatter())
                logging.getLogger().addHandler(streamhandler)
            try:
                Task(self.manager, job.task, options=job.options).execute()
            except TaskAbort as e:
                log.debug('task %s aborted: %r' % (job.task, e))
            finally:
                self.run_queue.task_done()
                if job.output:
                    job.output.close()
                    sys.stdout, sys.stderr = old_stdout, old_stderr
                    logging.getLogger().removeHandler(streamhandler)
                job.done()
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


class Job(object):
    """A job for the scheduler to execute."""
    #: Used to determine which job to run first when multiple jobs are waiting.
    priority = 1
    #: A datetime object when the job is scheduled to run. Jobs are sorted by this value when priority is the same.
    run_at = None
    #: The name of the task to execute
    task = None
    #: Options to run the task with
    options = None
    #: :class:`BufferQueue` to write the task execution output to. '[[END]]' will be sent to the queue when complete
    output = None

    def __init__(self, task, options=None, output=None):
        self.task = task
        self.options = options
        self.output = output
        self.run_at = datetime.now()
        # Lower priority if cron flag is present in either dict or Namespace form
        try:
            cron = self.options.cron
        except AttributeError:
            try:
                cron = self.options.get('cron')
            except AttributeError:
                cron = False
        if cron:
            self.priority = 5

    def start(self):
        """Called when the job is run."""
        pass

    def done(self):
        """Called when the job has finished running."""
        pass

    def __lt__(self, other):
        return (self.priority, self.run_at) < (other.priority, other.run_at)


class Trigger(object):
    def __init__(self, interval, tasks, options=None):
        self.tasks = tasks
        self.options = options
        self.execute_options = None
        self.unit = None
        self.amount = None
        self.on_day = None
        self.at_time = None
        self.last_run = None
        self.run_at = None
        self.interval = interval

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


class Tee(object):
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)


class BufferQueue(Queue.Queue):
    """Thread safe way to stream text. Reader should iterate over the buffer."""
    EOF = object()

    def write(self, line):
        self.put(line)

    def close(self):
        """The writing side should call this to indicate it is done streaming items."""
        self.put(self.EOF)

    def __iter__(self):
        """Iterates over the items written to the queue. Stops when writing side calls `close` method."""
        for line in iter(self.get, self.EOF):
            yield line


@event('config.register')
def register_config():
    register_config_key('schedules', main_schema)
