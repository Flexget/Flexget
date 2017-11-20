from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from time import sleep

import pytest

from flexget.entry import Entry
from flexget.plugins.list.thetvdb_list import TheTVDBSet


@pytest.mark.online
class TestTheTVDBList(object):
    config = """
      tasks: {}
    """

    tvdb_config = {'username': 'flexget2',
                   'account_id': 'D3405F10B200C4DB'}

    def test_thetvdb_list_add(self):
        tvdb_set = TheTVDBSet(self.tvdb_config)
        # Clearing existing list
        tvdb_set.clear()

        entry = Entry(title='Marvels Daredevil', tvdb_id='281662')

        assert entry not in tvdb_set
        tvdb_set.add(entry)

        sleep(2)
        assert entry in tvdb_set
