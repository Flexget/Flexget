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

        entry = task.find_entry(
            url='https://www.npostart.nl/zondag-met-lubach/09-11-2014/VPWON_1220631'
        )  # s01e01
        assert entry['npo_id'] == 'VPWON_1220631'
        assert entry['npo_url'] == 'https://www.npostart.nl/zondag-met-lubach/VPWON_1250334'
        assert entry['npo_name'] == 'Zondag met Lubach'
        assert (
            entry['npo_description']
            == 'Zeven dagen nieuws in dertig minuten, satirisch geremixt door Arjen Lubach. Met irrelevante verhalen van relevante gasten. Of andersom. Vanuit theater Bellevue in Amsterdam: platte inhoud en diepgravende grappen.'
        )
        assert entry['npo_runtime'] == '32'
        assert entry['npo_premium'] is False
        assert (
            entry['npo_version'] == 'NPO.release-1.43.1'
        )  # specify for which version of NPO website we did run this unittest

        entry = (
            task.find_entry(url='https://www.npostart.nl/14-01-2014/VARA_101348553') is None
        )  # episode with weird (and broken) URL and should be skipped
        entry = task.find_entry(
            url='https://www.npostart.nl/zembla/12-12-2013/VARA_101320582'
        )  # check that the next episode it there though
        assert entry['npo_id'] == 'VARA_101320582'
        assert entry['npo_url'] == 'https://www.npostart.nl/zembla/VARA_101377863'
        assert entry['npo_name'] == 'ZEMBLA'

        entry = task.find_entry(
            url='https://www.npostart.nl/typisch-overvecht/24-05-2018/BV_101388144'
        )
        assert entry['npo_id'] == 'BV_101388144'
        assert entry['npo_url'] == 'https://www.npostart.nl/typisch/BV_101386658'
        assert entry['npo_name'] == 'Typisch'

        entry = task.find_entry(
            url='https://www.npostart.nl/zembla/14-10-2007/VARA_101153941'
        )  # episode without a running time
        assert entry['npo_runtime'] == '0'

        assert (
            task.find_entry(url='https://www.npostart.nl/11-04-2014/KN_1656572') is None
        )  # episode without a name (and broken URL) that should be skipped

        assert (
            task.find_entry(
                url='https://www.npostart.nl/zondag-met-lubach-westeros-the-series/04-09-2017/WO_VPRO_10651334'
            )
            is None
        )  # a trailer for the series, that should not be listed


@pytest.mark.online
class TestNpoWatchlistPremium(object):
    config = """
        tasks:
          test:
            npo_watchlist:
              email: '8h3ga3+7nzf7xueal70o@sharklasers.com'
              password: 'Fl3xg3t!'
              download_premium: yes
    """

    def test_npowatchlist_lookup(self, execute_task):
        """npo_watchlist: Test npo watchlist lookup (ONLINE)"""

        task = execute_task('test')
        entry = task.find_entry(
            url='https://www.npostart.nl/dynasties/29-06-2021/POW_04072126'
        )  # a premium serie
        assert entry['npo_id'] == 'POW_04072126'
        assert entry['npo_url'] == 'https://www.npostart.nl/dynasties/POW_04005761'
        assert entry['npo_name'] == 'Dynasties'
        assert entry['npo_runtime'] == '50'
        assert entry['npo_premium'] is True


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

        entry = task.find_entry(
            url='https://www.npostart.nl/zondag-met-lubach/09-11-2014/VPWON_1220631'
        )  # s01e01
        assert entry['npo_language'] == 'nl'
        assert entry['language'] == 'nl'
        assert entry['tvdb_id'] == 288799
        assert entry['tvdb_language'] == 'nl'
