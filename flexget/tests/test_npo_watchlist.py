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
              email: 'chetrutrok@throwam.com'
              password: 'Fl3xg3t'
    """

    def test_info_lookup(self, execute_task):
        """npo_watchlist: Test Info Lookup (ONLINE)"""

        task = execute_task('test')

        entry = task.find_entry(url='http://www.npo.nl/als-de-dijken-breken/05-11-2016/VPWON_1243425')  # s01e01
        assert entry['npo_url'] == '/als-de-dijken-breken/VPWON_1261083'
        assert entry['npo_name'] == 'Als de dijken breken'
        assert entry['npo_description'] == 'Zesdelige dramaserie over hedendaagse watersnoodramp in Nederland en delen van Vlaanderen. Wat blijft er van Nederland over als nu de dijken breken? Met o.a. Gijs Scholten van Aschat, Susan Visser en Loek Peters.'
        assert entry['npo_language'] == 'nl'


@pytest.mark.online
class TestNpoWatchlistLanguageTheTVDBLookup(object):
    config = """
        tasks:
          test:
            npo_watchlist:
              email: 'chetrutrok@throwam.com'
              password: 'Fl3xg3t'
            thetvdb_lookup: yes
    """

    def test_info_lookup(self, execute_task):
        """npo_watchlist: Test Info Lookup (ONLINE)"""

        task = execute_task('test')

        entry = task.find_entry(url='http://www.npo.nl/als-de-dijken-breken/05-11-2016/VPWON_1243425')  # s01e01
        assert entry['npo_language'] == 'nl'
        assert entry['language'] == 'nl'
        assert entry['tvdb_id'] == 312980
        assert entry['tvdb_language'] == 'nl'
