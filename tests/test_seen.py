from __future__ import unicode_literals, division, absolute_import

from mock import patch

from flexget.manager import Session
from flexget.plugins.filter import seen
from flexget.plugins.filter.seen import SeenEntry, SeenField
from tests import FlexGetBase
from tests.test_api import APITest


class TestFilterSeen(FlexGetBase):
    __yaml__ = """
        templates:
          global:
            accept_all: true

        tasks:
          test:
            mock:
              - {title: 'Seen title 1', url: 'http://localhost/seen1'}

          test2:
            mock:
              - {title: 'Seen title 2', url: 'http://localhost/seen1'} # duplicate by url
              - {title: 'Seen title 1', url: 'http://localhost/seen2'} # duplicate by title
              - {title: 'Seen title 3', url: 'http://localhost/seen3'} # new

          test_number:
            mock:
              - {title: 'New title 1', url: 'http://localhost/new1', imdb_score: 5}
              - {title: 'New title 2', url: 'http://localhost/new2', imdb_score: 5}

          test_learn:
            mock:
            - title: learned entry
            accept_all: yes
            mock_output: yes
    """

    def test_seen(self):
        self.execute_task('test')
        assert self.task.find_entry(title='Seen title 1'), 'Test entry missing'
        # run again, should filter
        self.task.execute()
        assert not self.task.find_entry(title='Seen title 1'), 'Seen test entry remains'

        # execute another task
        self.execute_task('test2')
        # should not contain since fields seen in previous task
        assert not self.task.find_entry(title='Seen title 1'), 'Seen test entry 1 remains in second task'
        assert not self.task.find_entry(title='Seen title 2'), 'Seen test entry 2 remains in second task'
        # new item in task should exists
        assert self.task.find_entry(title='Seen title 3'), 'Unseen test entry 3 not in second task'

        # test that we don't filter reject on non-string fields (ie, seen same imdb_score)

        self.execute_task('test_number')
        assert self.task.find_entry(title='New title 1') and self.task.find_entry(title='New title 2'), \
            'Item should not have been rejected because of number field'

    def test_learn(self):
        self.execute_task('test_learn', options={'learn': True})
        assert len(self.task.accepted) == 1, 'entry should have been accepted'
        assert not self.task.mock_output, 'Entry should not have been output with --learn'
        self.execute_task('test_learn')
        assert len(self.task.rejected) == 1, 'Seen plugin should have rejected on second run'


class TestSeenLocal(FlexGetBase):
    __yaml__ = """
      templates:
        global:
          accept_all: yes
      tasks:
        global seen 1:
          mock:
          - title: item 1
        local seen:
          seen: local
          mock:
          - title: item 1
          - title: item 2
        global seen 2:
          mock:
          - title: item 1
          - title: item 2
    """

    def test_local(self):
        self.execute_task('global seen 1')
        # global seen 1 task should not affect seen in the local seen task
        self.execute_task('local seen')
        assert self.task.find_entry('accepted', title='item 1'), 'item 1 should be accepted first run'
        # seen should still work normally within the local seen task
        self.execute_task('local seen')
        assert self.task.find_entry('rejected', title='item 1'), 'item 1 should be seen on second run'
        # local seen task should not affect global seen 2 task, but global seen 1 should
        self.execute_task('global seen 2')
        assert self.task.find_entry('rejected', title='item 1'), 'item 1 should be seen'
        assert self.task.find_entry('accepted', title='item 2'), 'item 2 should be accepted'


class TestFilterSeenMovies(FlexGetBase):
    __yaml__ = """
        tasks:
          test_1:
            mock:
               - {title: 'Seen movie title 1', url: 'http://localhost/seen_movie1', imdb_id: 'tt0103064', tmdb_id: 123}
               - {title: 'Seen movie title 2', url: 'http://localhost/seen_movie2', imdb_id: 'tt0103064'}
            accept_all: yes
            seen_movies: loose

          test_2:
            mock:
              - {title: 'Seen movie title 3', url: 'http://localhost/seen_movie3', imdb_id: 'tt0103064'}
              - {title: 'Seen movie title 4', url: 'http://localhost/seen_movie4', imdb_id: 'tt0103064'}
              - {title: 'Seen movie title 5', url: 'http://localhost/seen_movie5', imdb_id: 'tt0231264'}
              - {title: 'Seen movie title 6', url: 'http://localhost/seen_movie6', tmdb_id: 123}
            seen_movies: loose

          strict:
            mock:
              - {title: 'Seen movie title 7', url: 'http://localhost/seen_movie7', imdb_id: 'tt0134532'}
              - {title: 'Seen movie title 8', url: 'http://localhost/seen_movie8', imdb_id: 'tt0103066'}
              - {title: 'Seen movie title 9', url: 'http://localhost/seen_movie9', tmdb_id: 456}
              - {title: 'Seen movie title 10', url: 'http://localhost/seen_movie10'}
            seen_movies: strict
    """

    def test_seen_movies(self):
        self.execute_task('test_1')
        assert not (self.task.find_entry(title='Seen movie title 1') and self.task.find_entry(
            title='Seen movie title 2')), 'Movie accepted twice in one run'

        # execute again
        self.task.execute()
        assert not self.task.find_entry(
            title='Seen movie title 1'), 'Test movie entry 1 should be rejected in second execution'
        assert not self.task.find_entry(
            title='Seen movie title 2'), 'Test movie entry 2 should be rejected in second execution'

        # execute another task
        self.execute_task('test_2')

        # should not contain since fields seen in previous task
        assert not self.task.find_entry(title='Seen movie title 3'), 'seen movie 3 exists'
        assert not self.task.find_entry(title='Seen movie title 4'), 'seen movie 4 exists'
        assert not self.task.find_entry(title='Seen movie title 6'), 'seen movie 6 exists (tmdb_id)'
        assert self.task.find_entry(title='Seen movie title 5'), 'unseen movie 5 doesn\'t exist'

    def test_seen_movies_strict(self):
        self.execute_task('strict')
        assert len(self.task.rejected) == 1, 'Too many movies were rejected'
        assert not self.task.find_entry(title='Seen movie title 10'), 'strict should not have passed movie 10'


class TestSeenAPI(APITest):
    @patch.object(seen, 'search')
    def test_seen_get(self, mock_seen_search):
        session = Session()
        entry_list = session.query(SeenEntry).join(SeenField).all()
        mock_seen_search.return_value = entry_list

        # No params
        rsp = self.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Default params
        rsp = self.get('/seen/?page=1&max=100&local_seen=true&sort_by=added&order=desc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Changed params
        rsp = self.get('/seen/?max=1000&local_seen=false&sort_by=title&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Negative test, invalid parameter
        rsp = self.get('/seen/?max=1000&local_seen=BLA&sort_by=title &order=asc')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        # With value
        rsp = self.get('/seen/?value=bla')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert mock_seen_search.call_count == 4, 'Should have 4 calls, is actually %s' % mock_seen_search.call_count
