from __future__ import unicode_literals, division, absolute_import
from datetime import timedelta, datetime

from flexget.manager import Session
from flexget.plugins.filter.movie_queue import queue_add, QueuedMovie
from tests import FlexGetBase


def age_last_emit(**kwargs):
    session = Session()
    for item in session.query(QueuedMovie).all():
        item.last_emit = datetime.utcnow() - timedelta(**kwargs)
    session.commit()


class TestEmitMovieQueue(FlexGetBase):
    __yaml__ = """
        tasks:
          test_default:
            emit_movie_queue: yes
          test_try_every:
            emit_movie_queue:
              try_every: 1 day
        """

    def test_default(self):
        queue_add(title='The Matrix 1999', imdb_id='tt0133093', tmdb_id=603)
        self.execute_task('test_default')
        assert len(self.task.entries) == 1
        # Movie ids should be provided on the entry without needing lookups
        entry = self.task.entries[0]
        assert entry.get('imdb_id', eval_lazy=False) == 'tt0133093'
        assert entry.get('tmdb_id', eval_lazy=False) == 603
        self.execute_task('test_default')
        assert len(self.task.entries) == 1, 'Movie should be emitted every run'

    def test_try_every(self):
        queue_add(title='The Matrix 1999', imdb_id='tt0133093')
        self.execute_task('test_try_every')
        assert len(self.task.entries) == 1
        age_last_emit(hours=12)
        self.execute_task('test_try_every')
        assert not self.task.entries, 'Movie should not be emitted until try_every has passed'
        age_last_emit(days=1)
        self.execute_task('test_try_every')
        assert len(self.task.entries) == 1, 'Movie should be emitted again after try_every has passed'
