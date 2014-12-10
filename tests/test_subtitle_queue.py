import datetime

from flexget.plugins.filter.subtitle_queue import queue_add, queue_get, SubtitleLanguages, QueuedSubtitle
from flexget.manager import Session
from tests import FlexGetBase


class TestSubtitleQueue(FlexGetBase):
    __yaml__ = """
         templates:
           global:
             mock:
               - {title: 'Movie', location: 'movie.mkv'}
               #- {title: 'Series', location: 'series.mkv'}
             accept_all: yes
             seen: local
         tasks:
           subtitle_add:
             subtitle_queue:
                action: add
           subtitle_emit:
             template: no_global
             subtitle_queue:
                action: emit
           subtitle_remove:
             subtitle_queue:
               action: remove
    """

    def test_subtitle_queue_add(self):
        self.execute_task('subtitle_add')
        assert len(self.task.entries) == 1

        entry = self.task.entries[0]
        assert entry.accepted

        queue = queue_get()
        assert len(queue) == 1

        self.execute_task('subtitle_add')
        assert len(self.task.entries) == 0, 'Movie should only be accepted once'

        queue = queue_get()
        assert len(queue) == 1

    def test_subtitle_queue_emit(self):
        config = {}
        config['languages'] = ['en']
        queue_add('./series.mkv', 'Series', config)
        queue_add('./movie.mkv', 'Movie', config)
        queue = queue_get()
        assert len(queue) == 2

        self.execute_task('subtitle_emit')

        assert len(self.task.entries) == 2, "2 items should be emitted from the queue."

        queue = queue_get()
        assert len(queue) == 2

        # self.execute_task('subtitle_emit')
        # print len(self.task.entries)
        # print len(queue_get())
        # assert len(self.task.entries) == 0, "2 items should be emitted from the queue again."

    def test_subtitle_queue_del(self):
        self.execute_task('subtitle_add')
        queue = queue_get()
        assert len(queue) == 1

        self.execute_task('subtitle_remove')
        queue = queue_get()
        assert len(queue) == 0

    def test_subtitle_queue_unique_lang(self):
        config = {}
        config['languages'] = ['en', 'eng']

        queue_add('./series.mkv', 'Series', config)
        queue_add('./movie.mkv', 'Movie', config)
        queue_add('./movie.mkv', 'Movie', config)

        with Session() as session:
            queue = queue_get(session=session)
            assert len(queue) == 2

            for q in queue:
                assert len(q.languages) == 1

    def test_subtitle_queue_old(self):
        config = {}
        config['stop_after'] = "7 days"

        queue_add('./series.mkv', 'Series', config)

        with Session() as session:
            s = session.query(QueuedSubtitle).first()
            s.added = datetime.datetime.now() + datetime.timedelta(-8)

        self.execute_task('subtitle_emit')
        assert len(self.task.entries) == 0, 'Old entry should not be emitted.'

        assert len(queue_get()) == 0, 'Old entry should have been removed.'

    def test_subtitle_queue_update(self):
        config = {}
        config['languages'] = ['en', 'eng']

        queue_add('./movie.mkv', 'Movie', config)
        assert queue_get()[0].stop_after == "7 days"

        config['stop_after'] = "15 days"
        queue_add('./movie.mkv', 'Movie', config)
        assert queue_get()[0].stop_after == "15 days", 'File\'s stop_after field should have been updated.'

