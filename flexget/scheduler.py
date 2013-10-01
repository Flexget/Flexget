from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
import logging
import Queue
import threading
import sys

from flexget.config_schema import register_config_key
from flexget.logger import FlexGetFormatter

log = logging.getLogger('scheduler')

UNITS = ['seconds', 'minutes', 'hours', 'days', 'weeks']
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


# TODO: make tests for this, the defaults probably don't work quite right at the moment
yaml_config = {
    'type': 'object',
    'properties': {
        'amount': {'type': 'number', 'default': 1},
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
        self.daemon = True
        self.run_queue = Queue.PriorityQueue()
        self.manager = manager
        self.periodic_jobs = []
        self._shutdown_now = False
        self._shutdown_when_finished = False

    def execute(self, task, options=None, output=None):
        """Add a task to the scheduler to be run immediately."""
        # Create a copy of task, so that changes to instance in manager thread do not affect scheduler thread
        job = ImmediateJob(task, options=options, output=output)
        self.run_queue.put(job)

    def add_scheduled_task(self, task, schedule):
        """Add a task to the scheduler to be run periodically on `schedule`."""
        job = PeriodicJob(task, schedule)
        with self.periodic_jobs_lock:
            self.periodic_jobs.append(job)

    def clear_scheduled_tasks(self):
        with self.periodic_jobs_lock:
            self.periodic_jobs = []

    def queue_pending_jobs(self):
        # Add pending jobs to the run queue
        with self.periodic_jobs_lock:
            for job in self.periodic_jobs:
                if job.should_run:
                    # Make sure it is not added to the queue again until it is done running
                    job.running = True
                    self.run_queue.put(job)

    def run(self):
        from flexget.task import Task
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
    priority = None
    #: A datetime object when the job is scheduled to run. Jobs are sorted by this value when priority is the same.
    run_at = None
    #: The name of the task to execute
    task = None
    #: Options to run the task with
    options = None
    #: :class:`BufferQueue` to write the task execution output to. '[[END]]' will be sent to the queue when complete
    output = None

    def start(self):
        """Called when the job is run."""
        pass

    def done(self):
        """Called when the job has finished running."""
        pass

    def __lt__(self, other):
        return (self.priority, self.run_at) < (other.priority, other.run_at)


class ImmediateJob(Job):
    priority = 1

    def __init__(self, task, options=None, output=None):
        self.task = task
        self.options = options
        self.output = output
        self.run_at = datetime.now()


class PeriodicJob(Job):
    priority = 5
    _schedule_attrs = ['unit', 'amount', 'on_day', 'at_time']

    def __init__(self, task, schedule, options=None):
        # Periodic jobs default to running with --cron
        if options is None:
            options = {'cron': True}
        self.task = task
        self.options = options
        self.running = False
        self.execute_options = None
        self.unit = None
        self.amount = None
        self.on_day = None
        self.at_time = None
        self.last_run = None
        self.run_at = None
        self.schedule = schedule

    @property
    def schedule(self):
        schedule = {}
        for key in self._schedule_attrs:
            schedule[key] = getattr(self, key)
        return schedule

    @schedule.setter
    def schedule(self, schedule):
        if not schedule:
            for attr in self._schedule_attrs:
                setattr(self, attr, None)
            return
        # Don't apply bad updates
        old_schedule = self.schedule
        try:
            self._validate()
        except ValueError:
            # We can't restore an invalid schedule
            old_schedule = None
        try:
            if isinstance(schedule, basestring):
                self._parse_schedule_text(schedule)
            else:
                invalid_keys = [k for k in schedule if k not in self._schedule_attrs]
                if invalid_keys:
                    raise ValueError('the following are not valid keys in a schedule dictionary: %s' %
                                     ', '.join(invalid_keys))
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
        if (self.on_day or self.at_time) and int(self.amount) != self.amount:
            raise ValueError('amount must be an integer when on_day or at_time are used')

    @property
    def should_run(self):
        return not self.running and self.run_at and datetime.now() >= self.run_at

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


class Tee(object):
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)


class BufferQueue(Queue.Queue):
    EOF = object()

    def write(self, txt):
        txt = txt.rstrip('\n')
        if txt:
            self.put(txt)

    def close(self):
        self.put(self.EOF)

    def __iter__(self):
        for line in iter(self.get, self.EOF):
            yield line


register_config_key('schedules', main_schema)
