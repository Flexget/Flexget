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

           movie_queue_different_queue_add:
             movie_queue:
               action: add
               queue_name: A new queue

           movie_queue_different_queue_accept:
             movie_queue:
               action: accept
               queue_name: A new queue

           movie_queue_different_queue_remove:
             movie_queue:
               action: remove
               queue_name: A new queue

           movie_queue_different_queue_forget:
             movie_queue:
               action: forget
               queue_name: A new queue

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

    def test_movie_queue_different_queue_add(self):
        self.execute_task('movie_queue_different_queue_add')
        queue = queue_get()
        assert len(queue) == 0
        queue = queue_get(queue_name='A new queue')
        assert len(queue) == 1

    def test_movie_queue_different_queue_accept(self):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603, queue_name='A new queue')
        self.execute_task('movie_queue_different_queue_accept')
        assert len(self.task.entries) == 1

        entry = self.task.entries[0]
        assert entry.get('imdb_id', eval_lazy=False) == 'tt1931533'
        assert entry.get('tmdb_id', eval_lazy=False) == 603

        self.execute_task('movie_queue_different_queue_accept')
        assert len(self.task.entries) == 0, 'Movie should only be accepted once'

    def test_movie_queue_different_queue_remove(self):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603, queue_name='A new queue')
        queue_add(title=u'KeepMe', imdb_id=u'tt1933533', tmdb_id=604, queue_name='A new queue')

        self.execute_task('movie_queue_different_queue_remove')

        assert len(self.task.entries) == 1

        queue = queue_get(queue_name='A new queue')
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1933533'
        assert entry.tmdb_id == 604

    def test_movie_queue_different_queue_forget(self):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603, queue_name='A new queue')
        self.execute_task('movie_queue_different_queue_accept')
        assert len(queue_get(downloaded=True, queue_name='A new queue')) == 1
        self.execute_task('movie_queue_different_queue_forget')
        assert not queue_get(downloaded=True, queue_name='A new queue')
        assert len(queue_get(queue_name='a New queue')) == 1


class TestMovieQueueAPI(APITest):
    mock_return_movie = {u'added': datetime.datetime(2015, 12, 30, 12, 32, 10, 688000),
                         u'tmdb_id': None, u'imdb_id': u'tt1234567', u'downloaded': None,
                         u'quality': u'', u'id': 181, u'entry_title': None,
                         u'title': u'The Top 14 Perform', u'entry_original_url': None,
                         u'entry_url': None, u'quality_req': u''}

    @patch.object(movie_queue, 'queue_get')
    def test_queue_get(self, mocked_queue_get):
        rsp = self.get('/movie_queue/?page=1&max=100&sort_by=added&order=desc')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        assert mocked_queue_get.called

        # Test using defaults
        rsp = self.get('/movie_queue/')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        assert mocked_queue_get.called

        # Sorting by attribute
        rsp = self.get('/movie_queue/?sort_by=added')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = self.get('/movie_queue/?sort_by=is_downloaded')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = self.get('/movie_queue/?sort_by=id')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = self.get('/movie_queue/?sort_by=title')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = self.get('/movie_queue/?sort_by=download_date')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        # Negative test
        rsp = self.get('/movie_queue/?sort_by=bla')
        assert rsp.status_code == 400, 'status code is actually %s' % rsp.status_code

        # Filtering by status
        rsp = self.get('/movie_queue/?is_downloaded=true')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = self.get('/movie_queue/?is_downloaded=false')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code

        # Sort order
        rsp = self.get('/movie_queue/?order=desc')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = self.get('/movie_queue/?order=asc')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code

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

        with_quality = {
            "title": "movie",
            "quality": "720p-1080p"
        }

        mocked_queue_add.return_value = self.mock_return_movie

        rsp = self.json_post('/movie_queue/', data=json.dumps(imdb_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code

        rsp = self.json_post('/movie_queue/', data=json.dumps(tmdb_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code

        rsp = self.json_post('/movie_queue/', data=json.dumps(title_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code

        rsp = self.json_post('/movie_queue/', data=json.dumps(with_quality))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code
        assert mocked_queue_add.call_count == 4

    @patch.object(movie_queue, 'get_movie_by_id')
    @patch.object(movie_queue, 'queue_forget')
    @patch.object(movie_queue, 'queue_edit')
    def test_queue_movie_put(self, mocked_queue_edit, mocked_queue_forget, mocked_get_movie_by_id):
        payload = {
            "reset_downloaded": True,
            "quality": "720p"
        }
        valid_response = {u'added': u'Wed, 30 Dec 2015 12:32:10 GMT', u'entry_title': None, u'tmdb_id': None,
                          u'title': u'The Top 14 Perform', u'entry_original_url': None, u'entry_url': None,
                          u'downloaded': None, u'quality_req': u'', u'imdb_id': u'tt1234567',
                          u'quality': u'',
                          u'id': 181}

        mocked_queue_edit.return_value = self.mock_return_movie
        mocked_queue_forget.return_value = self.mock_return_movie

        rsp = self.json_put('/movie_queue/1/', data=json.dumps(payload))

        assert json.loads(rsp.data) == valid_response, 'response data is %s' % json.loads(rsp.data)
        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code

        assert mocked_get_movie_by_id.called
        assert mocked_queue_edit.called
        assert mocked_queue_forget.called

    @patch.object(movie_queue, 'delete_movie_by_id')
    def test_queue_movie_del(self, delete_movie_by_id):
        rsp = self.delete('/movie_queue/7/')

        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code
        assert delete_movie_by_id.called

    @patch.object(movie_queue, 'get_movie_by_id')
    def test_queue_get_movie(self, mocked_get_movie_by_id):
        rsp = self.get('/movie_queue/7/')

        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code
        assert mocked_get_movie_by_id.called
