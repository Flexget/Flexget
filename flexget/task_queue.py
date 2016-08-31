from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import queue
import sys
import threading
import time

from sqlalchemy.exc import ProgrammingError, OperationalError

from flexget.task import TaskAbort

log = logging.getLogger('task_queue')


class TaskQueue(object):
    """
    Task processing thread.
    Only executes one task at a time, if more are requested they are queued up and run in turn.
    """

    def __init__(self):
        self.run_queue = queue.PriorityQueue()
        self._shutdown_now = False
        self._shutdown_when_finished = False

        self.current_task = None

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
                self.current_task = self.run_queue.get(timeout=0.5)
            except queue.Empty:
                if self._shutdown_when_finished:
                    self._shutdown_now = True
                continue
            try:
                self.current_task.execute()
            except TaskAbort as e:
                log.debug('task %s aborted: %r' % (self.current_task.name, e))
            except (ProgrammingError, OperationalError):
                log.critical('Database error while running a task. Attempting to recover.')
                self.current_task.manager.crash_report()
            except Exception:
                log.critical('BUG: Unhandled exception during task queue run loop.')
                self.current_task.manager.crash_report()
            finally:
                self.run_queue.task_done()
                self.current_task = None

        remaining_jobs = self.run_queue.qsize()
        if remaining_jobs:
            log.warning('task queue shut down with %s tasks remaining in the queue to run.' % remaining_jobs)
        else:
            log.debug('task queue shut down')

    def is_alive(self):
        return self._thread.is_alive()

    def put(self, task):
        """Adds a task to be executed to the queue."""
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
        if sys.version_info >= (3, 4):
            # Due to python bug, Thread.is_alive doesn't seem to work properly under our conditions on python 3.4+
            # http://bugs.python.org/issue26793
            # TODO: Is it important to have the clean abortion? Do we need to find a better way?
            self._thread.join()
            return
        try:
            while self._thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            log.error('Got ctrl-c, shutting down after running task (if any) completes')
            self.shutdown(finish_queue=False)
            # We still wait to finish cleanly, pressing ctrl-c again will abort
            while self._thread.is_alive():
                time.sleep(0.5)
