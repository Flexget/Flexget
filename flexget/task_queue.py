import queue
import threading
import time
from typing import Optional

from loguru import logger
from sqlalchemy.exc import OperationalError, ProgrammingError

from flexget.task import Task, TaskAbort

logger = logger.bind(name='task_queue')


class TaskQueue:
    """Task processing thread.

    Only executes one task at a time, if more are requested they are queued up and run in turn.
    """

    def __init__(self) -> None:
        self.run_queue: 'queue.PriorityQueue[Task]' = queue.PriorityQueue()
        self._shutdown_now = False
        self._shutdown_when_finished = False

        self.current_task: Optional[Task] = None
        self._thread = None

    def start(self) -> None:
        # We don't override `threading.Thread` because debugging this seems unsafe with pydevd.
        # Overriding __len__(self) seems to cause a debugger deadlock.
        # Don't instantiate the Thread() until `start()`, to make sure we have daemonized (forked) first.
        if not self._thread:
            self._thread = threading.Thread(target=self.run, name='task_queue', daemon=True)
        self._thread.start()

    def run(self) -> None:
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
                logger.debug('task {} aborted: {!r}', self.current_task.name, e)
            except (ProgrammingError, OperationalError):
                logger.critical('Database error while running a task. Attempting to recover.')
                self.current_task.manager.crash_report()
            except Exception:
                logger.critical('BUG: Unhandled exception during task queue run loop.')
                self.current_task.manager.crash_report()
            finally:
                self.run_queue.task_done()
                self.current_task = None

        remaining_jobs = self.run_queue.qsize()
        if remaining_jobs:
            logger.warning(
                'task queue shut down with {} tasks remaining in the queue to run.', remaining_jobs
            )
        else:
            logger.debug('task queue shut down')

    def is_alive(self) -> bool:
        return self._thread and self._thread.is_alive()

    def put(self, task: Task):
        """Adds a task to be executed to the queue."""
        self.run_queue.put(task)

    def __len__(self) -> int:
        return self.run_queue.qsize()

    def shutdown(self, finish_queue: bool = True) -> None:
        """Request shutdown.

        :param bool finish_queue: Should all tasks be finished before ending thread.
        """
        logger.debug('task queue shutdown requested')
        if finish_queue:
            self._shutdown_when_finished = True
            if self.run_queue.qsize():
                logger.verbose(
                    'There are {} tasks to execute. Shutdown will commence when they have completed.',
                    self.run_queue.qsize(),
                )
        else:
            self._shutdown_now = True

    def wait(self) -> None:
        """Waits for the thread to exit.

        Allows abortion of task queue with ctrl-c
        """
        try:
            while self._thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.error('Got ctrl-c, shutting down after running task (if any) completes')
            self.shutdown(finish_queue=False)
            # We still wait to finish cleanly, pressing ctrl-c again will abort
            while self._thread.is_alive():
                time.sleep(0.5)
