from __future__ import unicode_literals, division, absolute_import

import pytest

from flexget.entry import Entry
from flexget.plugins.list.trakt_list import TraktSet


@pytest.mark.online
class TestTraktList(object):
    config = """
      'tasks': {}
    """

    trakt_config = {'account': 'flexget_list_test',
                    'list': 'watchlist',
                    'type': 'shows'}

    def test_trakt_add(self):
        trakt_set = TraktSet(self.trakt_config)
        entry = Entry(title='White collar (2009)', series_name='White collar (2009)')

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set
