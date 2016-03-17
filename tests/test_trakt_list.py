from __future__ import unicode_literals, division, absolute_import

import pytest

from flexget.entry import Entry
from flexget.plugins.list.trakt_list import TraktSet


@pytest.mark.online
class TestTraktList(object):
    config = {'tasks': {}}

    trakt_config = {'account': 'flexget_list_test',
                    'list': 'watchlist',
                    'type': 'shows'}

    trakt_set = TraktSet(trakt_config)
    entry = Entry(title='White collar (2009)', series_name='White collar (2009)')
    trakt_set.add(entry)

