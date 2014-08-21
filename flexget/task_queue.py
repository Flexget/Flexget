import logging
import Queue
import threading
import time

from flexget.task import TaskAbort

log = logging.getLogger('task_queue')


class TaskQueue(threading.Thread):
    """
    Task processing thread.
    Only executes one task at a time, if more are requested they are queued up and run in turn.
    """
    def __init__(self):
        super(TaskQueue, self).__init__(name='task_queue')
        self.daemon = True
        self.run_queue = Queue.PriorityQueue()
        self._shutdown_now = False
        self._shutdown_when_finished = False

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
                task.execute()
            except TaskAbort as e:
                log.debug('task %s aborted: %r' % (task.name, e))
            finally:
                self.run_queue.task_done()
        remaining_jobs = self.run_queue.qsize()
        if remaining_jobs:
            log.warning('task queue shut down with %s tasks remaining in the queue to run.' % remaining_jobs)
        log.debug('task_queue run loop ended')

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
        else:
            self._shutdown_now = True

    def wait(self):
        """
        Waits for the thread to exit.
        Allows abortion of task queue with ctrl-c
        """
        try:
            while self.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            log.error('Got ctrl-c, shutting down after this task finishes')
            self.shutdown(finish_queue=False)
            # We still wait to finish cleanly, pressing ctrl-c again will abort
            while self.is_alive():
                time.sleep(0.5)
