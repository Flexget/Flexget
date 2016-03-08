from __future__ import unicode_literals, division, absolute_import
from datetime import timedelta, datetime

from flexget.manager import Session
from flexget.plugins.filter.movie_queue import queue_add, QueuedMovie


def age_last_emit(**kwargs):
    session = Session()
    for item in session.query(QueuedMovie).all():
        item.last_emit = datetime.utcnow() - timedelta(**kwargs)
    session.commit()


class TestEmitMovieQueue(object):
    config = """
        tasks:
          test_default:
            emit_movie_queue:
              # TODO: Currently plugin calls tmdb lookup to get year, movie queue should probably store
              year: no
          download_movie:
            mock:
            - title: The Matrix
              imdb_id: tt0133093
              tmdb_id: 603
            movie_queue: accept
          emit_from_separate_queue:
            emit_movie_queue:
              queue_name: queue 2
          download_movie_separate_queue:
            mock:
            - title: The Matrix
              imdb_id: tt0133093
              tmdb_id: 603
            movie_queue:
              action: accept
              queue_name: queue 2
        """

    def test_default(self, execute_task):
        queue_add(title='The Matrix 1999', imdb_id='tt0133093', tmdb_id=603)
        task = execute_task('test_default')
        assert len(task.entries) == 1
        # Movie ids should be provided on the entry without needing lookups
        entry = task.entries[0]
        assert entry.get('imdb_id', eval_lazy=False) == 'tt0133093'
        assert entry.get('tmdb_id', eval_lazy=False) == 603
        task = execute_task('test_default')
        assert len(task.entries) == 1, 'Movie should be emitted every run'

    def test_emit_undownloaded(self, execute_task):
        """Makes sure that items already downloaded are not emitted."""
        queue_add(title='The Matrix 1999', imdb_id='tt0133093', tmdb_id=603)
        task = execute_task('test_default')
        assert len(task.entries) == 1
        task = execute_task('download_movie')
        task = execute_task('test_default')
        assert len(task.entries) == 0, 'Should not emit already downloaded queue items.'

    def test_emit_different_queue(self, execute_task):
        queue_add(title='The Matrix 1999', imdb_id='tt0133093', tmdb_id=603)
        queue_add(title='The Matrix 1999', imdb_id='tt0133093', tmdb_id=603, queue_name='queue 2')

        task = execute_task('test_default')
        assert len(task.entries) == 1
        task = execute_task('emit_from_separate_queue')
        assert len(task.entries) == 1

        task = execute_task('download_movie_separate_queue')
        task = execute_task('test_default')
        assert len(task.entries) == 1
        task = execute_task('emit_from_separate_queue')
        assert len(task.entries) == 0
