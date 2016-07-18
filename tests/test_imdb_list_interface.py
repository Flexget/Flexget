from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin


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

        assert entry in imdb_set

    def test_imdb_list_remove(self):
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

        assert entry in imdb_set

        imdb_set.remove(entry)

        assert entry not in imdb_set

