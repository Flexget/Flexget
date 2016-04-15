from builtins import object
import datetime
import json

from mock import patch

from flexget.plugins.filter import movie_queue
from flexget.plugins.filter.movie_queue import queue_add, queue_get


class TestMovieQueue(object):
    config = """
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

    def test_movie_queue_accept(self, execute_task):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)
        task = execute_task('movie_queue_accept')
        assert len(task.entries) == 1

        entry = task.entries[0]
        assert entry.get('imdb_id', eval_lazy=False) == 'tt1931533'
        assert entry.get('tmdb_id', eval_lazy=False) == 603

        task = execute_task('movie_queue_accept')
        assert len(task.entries) == 0, 'Movie should only be accepted once'

    def test_movie_queue_add(self, execute_task):
        task = execute_task('movie_queue_add')

        assert len(task.entries) == 1

        queue = queue_get()
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1931533'
        assert entry.tmdb_id == 603
        assert entry.quality == 'any'

    def test_movie_queue_add_properties(self, execute_task):
        task = execute_task('movie_queue_add_properties')

        assert len(task.entries) == 1

        queue = queue_get()
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1931533'
        assert entry.tmdb_id == 603
        assert entry.quality == '720p'

    def test_movie_queue_remove(self, execute_task):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)
        queue_add(title=u'KeepMe', imdb_id=u'tt1933533', tmdb_id=604)

        task = execute_task('movie_queue_remove')

        assert len(task.entries) == 1

        queue = queue_get()
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1933533'
        assert entry.tmdb_id == 604

    def test_movie_queue_forget(self, execute_task):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)
        task = execute_task('movie_queue_accept')
        assert len(queue_get(downloaded=True)) == 1
        task = execute_task('movie_queue_forget')
        assert not queue_get(downloaded=True)
        assert len(queue_get()) == 1

    def test_movie_queue_different_queue_add(self, execute_task):
        task = execute_task('movie_queue_different_queue_add')
        queue = queue_get()
        assert len(queue) == 0
        queue = queue_get(queue_name='A new queue')
        assert len(queue) == 1

    def test_movie_queue_different_queue_accept(self, execute_task):
        default_queue = queue_get()
        named_queue = queue_get(queue_name='A new queue')
        assert len(default_queue) == len(named_queue) == 0

        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603, queue_name='A new queue')
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603)

        default_queue = queue_get()
        named_queue = queue_get(queue_name='A new queue')
        assert len(named_queue) == len(default_queue) == 1

        task = execute_task('movie_queue_different_queue_accept')
        assert len(task.entries) == 1

        entry = task.entries[0]
        assert entry.get('imdb_id', eval_lazy=False) == 'tt1931533'
        assert entry.get('tmdb_id', eval_lazy=False) == 603

        default_queue = queue_get()
        named_queue = queue_get(queue_name='A new queue', downloaded=False)
        assert len(named_queue) == 0
        assert len(default_queue) == 1

        task = execute_task('movie_queue_different_queue_accept')
        assert len(task.entries) == 0, 'Movie should only be accepted once'

    def test_movie_queue_different_queue_remove(self, execute_task):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603, queue_name='A new queue')
        queue_add(title=u'KeepMe', imdb_id=u'tt1933533', tmdb_id=604, queue_name='A new queue')

        task = execute_task('movie_queue_different_queue_remove')

        assert len(task.entries) == 1

        queue = queue_get(queue_name='A new queue')
        assert len(queue) == 1

        entry = queue[0]
        assert entry.imdb_id == 'tt1933533'
        assert entry.tmdb_id == 604

    def test_movie_queue_different_queue_forget(self, execute_task):
        queue_add(title=u'MovieInQueue', imdb_id=u'tt1931533', tmdb_id=603, queue_name='A new queue')
        task = execute_task('movie_queue_different_queue_accept')
        assert len(queue_get(downloaded=True, queue_name='A new queue')) == 1
        task = execute_task('movie_queue_different_queue_forget')
        assert not queue_get(downloaded=True, queue_name='A new queue')
        assert len(queue_get(queue_name='a New queue')) == 1


class TestMovieQueueAPI(object):

    config = 'tasks: {}'

    mock_return_movie = {u'added': datetime.datetime(2015, 12, 30, 12, 32, 10, 688000),
                         u'tmdb_id': None, u'imdb_id': u'tt1234567', u'downloaded': None,
                         u'quality': u'', u'id': 181, u'entry_title': None,
                         u'title': u'The Top 14 Perform', u'entry_original_url': None,
                         u'entry_url': None, u'quality_req': u''}

    @patch.object(movie_queue, 'queue_get')
    def test_queue_get(self, mocked_queue_get, api_client):
        rsp = api_client.get('/movie_queue/?page=1&max=100&sort_by=added&order=desc')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        assert mocked_queue_get.called

        # Test using defaults
        rsp = api_client.get('/movie_queue/')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        assert mocked_queue_get.called

        # Sorting by attribute
        rsp = api_client.get('/movie_queue/?sort_by=added')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = api_client.get('/movie_queue/?sort_by=is_downloaded')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = api_client.get('/movie_queue/?sort_by=id')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = api_client.get('/movie_queue/?sort_by=title')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = api_client.get('/movie_queue/?sort_by=download_date')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        # Negative test
        rsp = api_client.get('/movie_queue/?sort_by=bla')
        assert rsp.status_code == 400, 'status code is actually %s' % rsp.status_code

        # Filtering by status
        rsp = api_client.get('/movie_queue/?is_downloaded=true')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = api_client.get('/movie_queue/?is_downloaded=false')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code

        # Sort order
        rsp = api_client.get('/movie_queue/?order=desc')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code
        rsp = api_client.get('/movie_queue/?order=asc')
        assert rsp.status_code == 200, 'status code is actually %s' % rsp.status_code

    @patch.object(movie_queue, 'queue_add')
    def test_queue_add(self, mocked_queue_add, api_client):
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

        rsp = api_client.json_post('/movie_queue/', data=json.dumps(imdb_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code

        rsp = api_client.json_post('/movie_queue/', data=json.dumps(tmdb_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code

        rsp = api_client.json_post('/movie_queue/', data=json.dumps(title_movie))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code

        rsp = api_client.json_post('/movie_queue/', data=json.dumps(with_quality))
        assert rsp.status_code == 201, 'response code should be 201, is actually %s' % rsp.status_code
        assert mocked_queue_add.call_count == 4

    @patch.object(movie_queue, 'get_movie_by_id')
    @patch.object(movie_queue, 'queue_forget')
    @patch.object(movie_queue, 'queue_edit')
    def test_queue_movie_put(self, mocked_queue_edit, mocked_queue_forget, mocked_get_movie_by_id, api_client):
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

        rsp = api_client.json_put('/movie_queue/1/', data=json.dumps(payload))

        assert json.loads(rsp.get_data(as_text=True)) == valid_response
        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code

        assert mocked_get_movie_by_id.called
        assert mocked_queue_edit.called
        assert mocked_queue_forget.called

    @patch.object(movie_queue, 'delete_movie_by_id')
    def test_queue_movie_del(self, delete_movie_by_id, api_client):
        rsp = api_client.delete('/movie_queue/7/')

        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code
        assert delete_movie_by_id.called

    @patch.object(movie_queue, 'get_movie_by_id')
    def test_queue_get_movie(self, mocked_get_movie_by_id, api_client):
        rsp = api_client.get('/movie_queue/7/')

        assert rsp.status_code == 200, 'response code should be 200, is actually %s' % rsp.status_code
        assert mocked_get_movie_by_id.called
