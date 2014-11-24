from flexget.plugins.filter.movie_queue import queue_add, queue_get
from tests import FlexGetBase


class TestMovieQueue(FlexGetBase):
    __yaml__ = """
         templates:
           global:
             mock:
               - {title: 'MovieInQueue', imdb_id: 'tt1931533', tmdb_id: 603, movie_name: MovieInQueue}
             accept_all: yes
             seen: local
         tasks:
           movie_queue_accept:
             movie_queue: accept

           movie_queue_add:
             movie_queue: add

           movie_queue_add_properties:
             movie_queue:
               action: add
               quality: 720p

           movie_queue_remove:
             movie_queue: remove

           movie_queue_forget:
             movie_queue: forget
    """

    def test_movie_queue_accept(self):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)
        self.execute_task('movie_queue_accept')
        assert len(self.task.entries) == 1

        entry = self.task.entries[0]
        assert entry.get('imdb_id', eval_lazy=False) == 'tt1931533'
        assert entry.get('tmdb_id', eval_lazy=False) == 603

        self.execute_task('movie_queue_accept')
        assert len(self.task.entries) == 0, 'Movie should only be accepted once'

    def test_movie_queue_add(self):
        self.execute_task('movie_queue_add')

        assert len(self.task.entries) == 1

        queue = queue_get()
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1931533'
        assert entry.tmdb_id == 603
        assert entry.quality == 'any'

    def test_movie_queue_add_properties(self):
        self.execute_task('movie_queue_add_properties')

        assert len(self.task.entries) == 1

        queue = queue_get()
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1931533'
        assert entry.tmdb_id == 603
        assert entry.quality == '720p'

    def test_movie_queue_remove(self):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)
        queue_add(title=u'KeepMe', imdb_id=u'tt1933533', tmdb_id=604)

        self.execute_task('movie_queue_remove')

        assert len(self.task.entries) == 1

        queue = queue_get()
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1933533'
        assert entry.tmdb_id == 604

    def test_movie_queue_forget(self):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)
        self.execute_task('movie_queue_accept')
        assert len(queue_get(downloaded=True)) == 1
        self.execute_task('movie_queue_forget')
        assert not queue_get(downloaded=True)
        assert len(queue_get()) == 1
