from __future__ import absolute_import, division, unicode_literals

import logging
import Queue
import threading
import time
from datetime import datetime

from collections import MutableMapping

from sqlalchemy.exc import ProgrammingError, OperationalError

from flexget.task import TaskAbort

log = logging.getLogger('task_queue')


class TaskList(MutableMapping):
    """Acts like a normal dict, but tasks will only be keep for a specific amount of time."""

    def __init__(self):
        self._store = dict()
        self._max = 15

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        if len(self._store) >= self._max:
            # Delete tasks older then 1 hr
            clear = len(self._store) - self._max
            # TODO: Prob a more efficient way to do this
            now = datetime.now()
            for i, task_id in enumerate(self._store.keys()):
                if i >= clear:
                    break
                diff = (now - self._store[task_id]['finished'])
                if self._store[task_id]['status'] == 'finished' and diff.seconds >= 3600:
                    self.__delitem__(task_id)

        self._store[key] = value

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        # Uses our getitem to skip expired items
        return (key for key in self._store.keys())

    def __len__(self):
        return len(list(self.__iter__()))

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, dict(zip(self._store, (v[1] for v in self._store.values()))))

    def add(self, task):
        self[task.id] = {
            'id': task.id,
            'name': task.name,
            'status': 'pending',
            'created': datetime.now(),
            'started': None,
            'finished': None,
            'message': '',
        }

    def started(self, task):
        self._store[task.id]['status'] = 'running'
        self._store[task.id]['started'] = datetime.now()

    def finish(self, task):
        self._store[task.id]['status'] = "finished"
        self._store[task.id]['finished'] = datetime.now()

        stats = (len(task.accepted), len(task.rejected), len(task.undecided), len(task.failed))
        self._store[task.id]['message'] = 'Accepted: %s Rejected: %s Undecided: %s Failed: %s' % stats

    def aborted(self, task, reason):
        self._store[task.id]['status'] = "aborted"
        self._store[task.id]['finished'] = datetime.now()
        self._store[task.id]['message'] = reason


class TaskQueue(object):
    """
    Task processing thread.
    Only executes one task at a time, if more are requested they are queued up and run in turn.
    """
    def __init__(self):
        self.tasks_data = TaskList()
        self.run_queue = Queue.PriorityQueue()
        self._shutdown_now = False
        self._shutdown_when_finished = False

        # We don't override `threading.Thread` because debugging this seems unsafe with pydevd.
        # Overriding __len__(self) seems to cause a debugger deadlock.
        self._thread = threading.Thread(target=self.run, name='task_queue')
        self._thread.daemon = True

    def start(self):
        self._thread.start()

    def run(self):
        while not self._shutdown_now:
            # Grab the first job from the run queue and do it
            try:
                task = self.run_queue.get(timeout=0.5)
            except Queue.Empty:
                if self._shutdown_when_finished:
                    self._shutdown_now = True
                continue
            try:
                self.tasks_data.started(task)
                task.execute()
                self.tasks_data.finish(task)
            except TaskAbort as e:
                self.tasks_data.aborted(task, e.reason)
                log.debug('task %s aborted: %r' % (task.name, e))
            except (ProgrammingError, OperationalError):
                log.critical('Database error while running a task. Attempting to recover.')
                task.manager.crash_report()
            except Exception:
                log.critical('BUG: Unhandled exception during task queue run loop.')
                task.manager.crash_report()
            finally:
                self.run_queue.task_done()
        remaining_jobs = self.run_queue.qsize()
        if remaining_jobs:
            log.warning('task queue shut down with %s tasks remaining in the queue to run.' % remaining_jobs)
        else:
            log.debug('task queue shut down')

    def is_alive(self):
        return self._thread.is_alive()

    def put(self, task):
        """Adds a task to be executed to the queue."""
        self.tasks_data.add(task)
        self.run_queue.put(task)

    def __len__(self):
        return self.run_queue.qsize()

    def shutdown(self, finish_queue=True):
        """
        Request shutdown.

        :param bool finish_queue: Should all tasks be finished before ending thread.
        """
        log.debug('task queue shutdown requested')
        if finish_queue:
            self._shutdown_when_finished = True
            if self.run_queue.qsize():
                log.verbose('There are %s tasks to execute. Shutdown will commence when they have completed.' %
                            self.run_queue.qsize())
        else:
            self._shutdown_now = True

    def wait(self):
        """
        Waits for the thread to exit.
        Allows abortion of task queue with ctrl-c
        """
        try:
            while self._thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            log.error('Got ctrl-c, shutting down after running task (if any) completes')
            self.shutdown(finish_queue=False)
            # We still wait to finish cleanly, pressing ctrl-c again will abort
            while self._thread.is_alive():
                time.sleep(0.5)
