import datetime
import json

from mock import patch

from flexget.plugins.filter import movie_queue
from flexget.plugins.filter.movie_queue import queue_add, queue_get
from tests import FlexGetBase
from tests.test_api import APITest


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


class TestMovieQueueAPI(APITest):
    mock_return_movie = {u'added': datetime.datetime(2015, 12, 30, 12, 32, 10, 688000),
                         u'tmdb_id': None, u'imdb_id': u'tt1234567', u'downloaded': None,
                         u'quality': u'', u'id': 181, u'entry_title': None,
                         u'title': u'The Top 14 Perform', u'entry_original_url': None,
                         u'entry_url': None, u'quality_req': u''}

    @patch.object(movie_queue, 'queue_get')
    def test_queue_get(self, mocked_queue_get):
        rsp = self.get('/movie_queue/?max=100&downloaded_only=false&order=desc&page=1&sort_by=added')
        assert rsp.status_code == 200
        assert mocked_queue_get.called

        # Test using defaults
        rsp = self.get('/movie_queue/')
        assert rsp.status_code == 200
        assert mocked_queue_get.called

    @patch.object(movie_queue, 'queue_add')
    def test_queue_add(self, mocked_queue_add):
        imdb_movie = {
            "imdb_id": "tt1234567"
        }
        tmdb_movie = {
            "tmdb_id": 1234567
        }
        title_movie = {
            "title": "movie"
        }

        mocked_queue_add.return_value = self.mock_return_movie

        rsp = self.json_post('/movie_queue/', data=json.dumps(imdb_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code
        assert mocked_queue_add.called

        rsp = self.json_post('/movie_queue/', data=json.dumps(tmdb_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code
        assert mocked_queue_add.called

        rsp = self.json_post('/movie_queue/', data=json.dumps(title_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code
        assert mocked_queue_add.called

    @patch.object(movie_queue, 'queue_forget')
    @patch.object(movie_queue, 'queue_edit')
    def test_queue_movie_put(self, mocked_queue_edit, mocked_queue_forget):
        payload = {
            "reset_downloaded": True,
            "quality": "720p"
        }
        valid_response = {u'status': u'success',
                          u'movie': {u'added': u'Wed, 30 Dec 2015 12:32:10 GMT', u'entry_title': None, u'tmdb_id': None,
                                     u'title': u'The Top 14 Perform', u'entry_original_url': None, u'entry_url': None,
                                     u'downloaded': None, u'quality_req': u'', u'imdb_id': u'tt1234567',
                                     u'quality': u'',
                                     u'id': 181},
                          u'message': u'Successfully updated movie details'}

        mocked_queue_edit.return_value = self.mock_return_movie
        mocked_queue_forget.return_value = self.mock_return_movie

        rsp = self.json_put('/movie_queue/imdb/tt1234567/', data=json.dumps(payload))

        assert json.loads(rsp.data) == valid_response, 'response data is %s' % json.loads(rsp.data)
        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code

        assert mocked_queue_edit.called
        assert mocked_queue_forget.called

    @patch.object(movie_queue, 'queue_del')
    def test_queue_movie_del(self, mocked_queue_del):
        rsp = self.delete('/movie_queue/imdb/tt1234567/')

        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code
        assert mocked_queue_del.called
