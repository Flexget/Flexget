from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import time

import pytest

from flexget.entry import Entry
from flexget.plugins.list.imdb_list import ImdbEntrySet


@pytest.mark.online
class TestIMDBList(object):
    config = """
      tasks: {}
    """

    imdb_config = {'login': 'siysbijz@sharklasers.com',
                   'password': 'flexget16',
                   'list': 'watchlist'}

    imdb = None

    @pytest.fixture(scope='class')
    def imdb_set(cls):
        if not cls.imdb:
            cls.imdb = ImdbEntrySet(cls.imdb_config)

        return cls.imdb

    def test_imdb_list_add(self, imdb_set):
        # Clearing existing list
        imdb_set.clear()

        entry = Entry(title='the matrix', imdb_id='tt0133093')

        assert entry not in imdb_set
        imdb_set.add(entry)

        time.sleep(10)
        assert entry in imdb_set

    def test_imdb_list_remove(self, imdb_set):
        # Clearing existing list
        imdb_set.clear()

        entry = Entry(title='the matrix', imdb_id='tt0133093')

        assert entry not in imdb_set
        imdb_set.add(entry)

        time.sleep(10)
        assert entry in imdb_set

        time.sleep(10)
        imdb_set.remove(entry)
        assert entry not in imdb_set

