# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import PY3

import mock
import pytest

from flexget.manager import Session
from flexget.plugins.input.npo_watchlist import NPOWatchlist


@pytest.mark.online
class TestNpoWatchlistInfo(object):
    config = """
        tasks:
          test:
            npo_watchlist:
              email: '8h3ga3+7nzf7xueal70o@sharklasers.com'
              password: 'Fl3xg3t!'
    """

    def test_npowatchlist_lookup(self, execute_task):
        """npo_watchlist: Test npo watchlist lookup (ONLINE)"""

        task = execute_task('test')

        entry = task.find_entry(url='https://www.npo.nl/als-de-dijken-breken/05-11-2016/VPWON_1243425')  # s01e01
        assert entry['npo_url'] == 'https://www.npo.nl/als-de-dijken-breken/VPWON_1261083'
        assert entry['npo_name'] == 'Als de dijken breken'
        assert entry['npo_description'] == 'Serie over een hedendaagse watersnoodramp in Nederland en delen van Vlaanderen.'
        assert entry['npo_runtime'] == '46'

        assert task.find_entry(url='https://www.npo.nl/als-de-dijken-breken-official-trailer-2016/26-10-2016/POMS_EO_5718640') is None  # a trailer for the series, that should not be listed


@pytest.mark.online
class TestNpoWatchlistLanguageTheTVDBLookup(object):
    config = """
        tasks:
          test:
            npo_watchlist:
              email: '8h3ga3+7nzf7xueal70o@sharklasers.com'
              password: 'Fl3xg3t!'
            thetvdb_lookup: yes
    """

    def test_tvdblang_lookup(self, execute_task):
        """npo_watchlist: Test npo_watchlist tvdb language lookup (ONLINE)"""

        task = execute_task('test')

        entry = task.find_entry(url='https://www.npo.nl/als-de-dijken-breken/05-11-2016/VPWON_1243425')  # s01e01
        assert entry['npo_language'] == 'nl'
        assert entry['language'] == 'nl'
        assert entry['tvdb_id'] == 312980
        assert entry['tvdb_language'] == 'nl'
