import threading
import time

from flexget.components.scheduler import scheduler
from flexget.task_queue import TaskQueue


def test_has_died_is_false_before_the_queue_is_started():
    # Distinct from `not is_alive()`, which is also true here.
    assert TaskQueue().has_died() is False


def test_has_died_tracks_the_thread():
    queue = TaskQueue()
    queue.start()
    assert queue.has_died() is False
    queue.shutdown(finish_queue=True)
    queue._thread.join(timeout=10)
    assert queue.has_died() is True


class _DeadQueue:
    def has_died(self):
        return True


class _FakeManager:
    """A manager whose queue thread died mid-task, so finished_event is never set."""

    task_queue = _DeadQueue()

    def execute(self, options=None, priority=1, suppress_warnings=None):
        return [('some-id', 'sometask', threading.Event())]


def test_run_job_gives_up_when_the_task_queue_dies(monkeypatch):
    """An unbounded wait here pins the apscheduler job instance forever."""
    monkeypatch.setattr(scheduler, 'manager', _FakeManager())
    monkeypatch.setattr(scheduler, 'QUEUE_LIVENESS_INTERVAL', 0.01)
    started = time.monotonic()
    scheduler.run_job(['sometask'])
    assert time.monotonic() - started < 10
