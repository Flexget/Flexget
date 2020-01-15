from time import sleep

import pytest

from flexget.components.managed_lists.lists.thetvdb_list import TheTVDBSet
from flexget.entry import Entry


@pytest.mark.online
class TestTheTVDBList:
    config = """
      tasks: {}
    """

    tvdb_config = {
        'username': 'flexget2',
        'account_id': 'D3405F10B200C4DB',
        'api_key': '4D297D8CFDE0E105',
    }

    def test_thetvdb_list_add(self, manager):
        # manager fixture is requested so that the database is spun up
        tvdb_set = TheTVDBSet(self.tvdb_config)
        # Clearing existing list
        tvdb_set.clear()

        entry = Entry(title='Marvels Daredevil', tvdb_id='281662')

        assert entry not in tvdb_set
        tvdb_set.add(entry)

        sleep(2)
        assert entry in tvdb_set
