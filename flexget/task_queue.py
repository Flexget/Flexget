from __future__ import absolute_import, division, unicode_literals

import logging
import Queue
import threading
import time
from datetime import datetime


from sqlalchemy.exc import ProgrammingError, OperationalError

from flexget.task import TaskAbort

log = logging.getLogger('task_queue')


class TaskInfo(object):

    def __init__(self, task):
        self.id = task.id
        self.name = task.name
        self.status = 'pending'
        self.created = datetime.now()
        self.started = None
        self.finished = None
        self.message = ''

    @property
    def running(self):
        return self.status == 'running'

    def start(self):
        self.status = 'running'
        self.started = datetime.now()

    def finish(self, entries):
        self.status = "finished"
        self.finished = datetime.now()

        stats = (len(entries.accepted), len(entries.rejected), len(entries.undecided), len(entries.failed))
        self.message = 'Accepted: %s Rejected: %s Undecided: %s Failed: %s' % stats

    def aborted(self, reason):
        self.status = "aborted"
        self.finished = datetime.now()
        self.message = reason


class TaskQueue(object):
    """
    Task processing thread.
    Only executes one task at a time, if more are requested they are queued up and run in turn.
    """
    def __init__(self):
        self.tasks_info = {}
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
                task_info = self.tasks_info[task.id]
            except Queue.Empty:
                if self._shutdown_when_finished:
                    self._shutdown_now = True
                continue
            try:
                task_info.start()
                task.execute()
                task_info.finish(task.all_entries)
            except TaskAbort as e:
                task_info.aborted(e.reason)
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
        if len(self.tasks_info) >= 15:
            # Delete tasks older then 1 hr
            clear = len(self.tasks_info) - 15
            now = datetime.now()
            for i, task_id in enumerate(self.tasks_info.keys()):
                task_info = self.tasks_info[task_id]
                if i >= clear:
                    break
                if task_info.status == 'finished' and (now - task_info.finished).seconds >= 3600:
                    del self.tasks_info[task_id]

        self.tasks_info[task.id] = TaskInfo(task)
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
