from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import time

import pytest

from flexget.entry import Entry
from flexget.plugins.list.imdb_list import ImdbEntrySet


@pytest.mark.online
@pytest.mark.skip(reason='IMDB Tests are far too unreliable')
class TestIMDBList(object):
    config = """
      tasks: {}
    """

    imdb_config = {'login': 'siysbijz@sharklasers.com',
                   'password': 'flexget16',
                   'list': 'watchlist'}

    def test_imdb_list_add(self):
        imdb_set = ImdbEntrySet(self.imdb_config)
        # Clearing existing list
        imdb_set.clear()

        entry = Entry(title='the matrix', imdb_id='tt0133093')

        assert entry not in imdb_set
        imdb_set.add(entry)

        # pls no caching
        imdb_set.session.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        imdb_set.session.headers['Pragma'] = 'no-cache'
        imdb_set.session.headers['Expires'] = '0'

        # Add delay as imdb seems to cache
        time.sleep(5)
        assert entry in imdb_set

    def test_imdb_list_remove(self):
        imdb_set = ImdbEntrySet(self.imdb_config)
        # Clearing existing list
        imdb_set.clear()

        entry = Entry(title='the matrix', imdb_id='tt0133093')

        assert entry not in imdb_set
        imdb_set.add(entry)

        # Add delay as imdb seems to cache
        time.sleep(5)
        assert entry in imdb_set

        imdb_set.remove(entry)

        # Add delay as imdb seems to cache
        time.sleep(5)
        assert entry not in imdb_set


@pytest.mark.online
@pytest.mark.skip(reason='IMDB Tests are far too unreliable')
class TestIMDBListTypes(object):
    imdb_config = {'login': 'siysbijz@sharklasers.com',
                   'password': 'flexget16',
                   'list': 'watchlist'}

    config = """
        tasks:
          imdb_list_add:
            mock:
              - {title: 'the matrix', url: 'http://localhost/seen1', imdb_id: 'tt0133093'}
              - {title: 'black mirror', url: 'http://localhost/seen2', imdb_id: 'tt2085059'}
            accept_all: yes
            list_add:
              - imdb_list:
                  login: 'siysbijz@sharklasers.com'
                  password: 'flexget16'
                  list: 'watchlist'

          imdb_list_get:
            imdb_list:
              login: 'siysbijz@sharklasers.com'
              password: 'flexget16'
              list: 'watchlist'
            accept_all: yes
    """

    def test_imdb_list_types(self, execute_task):
        imdb_set = ImdbEntrySet(self.imdb_config)
        # Clearing existing list
        imdb_set.clear()

        task = execute_task('imdb_list_add')
        assert len(task.accepted) == 2

        task = execute_task('imdb_list_get')
        assert len(task.accepted) == 2
        assert task.find_entry(movie_name='The Matrix', movie_year=1999)
        assert task.find_entry(series_name='Black Mirror', series_year=2011)
