from flexget.plugins.filter.subtitle_queue import queue_add, queue_get
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
           movie_queue_remove:
             movie_queue: remove
           movie_queue_forget:
             movie_queue: forget
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

        self.execute_task('subtitle_emit')

        assert len(self.task.entries) == 2, "2 items should be in queue."

    def test_subtitle_queue_del(self):
        self.execute_task('subtitle_add')
        queue = queue_get()
        assert len(queue) == 1

        self.execute_task('subtitle_remove')
        queue = queue_get()
        assert len(queue) == 0
