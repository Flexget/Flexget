from __future__ import unicode_literals, division, absolute_import

import pytest

from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.api_trakt import TraktUserAuth
from flexget.plugins.list.trakt_list import TraktSet


@pytest.mark.online
class TestTraktList(object):
    """
    Credentials for test account are:
       username: flexget_list_test
       password: flexget
    """

    config = """
      'tasks': {}
    """

    trakt_config = {'account': 'flexget_list_test',
                    'list': 'watchlist',
                    'type': 'shows'}

    def get_auth(self):
        kwargs = {
            'account': 'flexget_list_test',
            'access_token': '895b5417b640ed0d40b5fbda56a3ad2158fc36f313c825f638e61b65586df32d',
            'refresh_token': '3708a9f1057c10c0a9b59f544e6c758000d02b7d1cc66b9404e8d70210d15cba',
            'created': 1458488839.44,
            'expires': 7776000
        }
        # Creates the trakt token in db
        with Session() as session:
            auth = TraktUserAuth(**kwargs)
            session.add(auth)
            session.commit()

    def test_trakt_add(self):
        self.get_auth()
        trakt_set = TraktSet(self.trakt_config)

        entry = Entry(title='White collar (2009)', series_name='White collar (2009)')

        assert entry not in trakt_set

        trakt_set.add(entry)
        assert entry in trakt_set
