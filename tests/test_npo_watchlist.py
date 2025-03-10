import pytest


@pytest.mark.online
@pytest.mark.xdist_group(name="npo_watchlist")
class TestNpoWatchlistInfo:
    config = """
        tasks:
          test:
            npo_watchlist:
              email: '8h3ga3+7nzf7xueal70o@sharklasers.com'
              password: 'Fl3xg3t!'
    """

    def test_npowatchlist_lookup(self, execute_task):
        """npo_watchlist: Test npo watchlist lookup (ONLINE)."""
        task = execute_task('test')

        entry = task.find_entry(
            url='https://www.npostart.nl/zondag-met-lubach/09-11-2014/VPWON_1220631'
        )  # s01e01
        assert entry['npo_id'] == 'VPWON_1220631'
        assert entry['npo_url'] == 'https://www.npostart.nl/zondag-met-lubach/VPWON_1250334'
        assert entry['npo_name'] == 'Zondag met Lubach'
        assert (
            entry['npo_description']
            == 'Zeven dagen nieuws in dertig minuten, satirisch geremixt door Arjen Lubach. Nog actueler, nog satirischer en nog vaker nog het woord nog.'
        )
        assert entry['npo_runtime'] == '32'
        assert entry['npo_premium'] is False
        assert (
            entry['npo_version'] == 'NPO.6586736ba8ccc16e4f9288118f71dbd3c81e21e8'
        )  # specify for which version of NPO website we did run this unittest

        entry = (
            task.find_entry(url='https://www.npostart.nl/14-01-2014/VARA_101348553') is None
        )  # episode with weird (and broken) URL and should be skipped
        entry = task.find_entry(
            url='https://www.npostart.nl/zembla/12-12-2013/VARA_101320582'
        )  # check that the next episode it there though
        assert entry['npo_id'] == 'VARA_101320582'
        assert entry['npo_url'] == 'https://www.npostart.nl/zembla/VARA_101377863'
        assert entry['npo_name'] == 'Zembla'

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
@pytest.mark.xdist_group(name="npo_watchlist")
class TestNpoWatchlistPremium:
    config = """
        tasks:
          test:
            npo_watchlist:
              email: '8h3ga3+7nzf7xueal70o@sharklasers.com'
              password: 'Fl3xg3t!'
              download_premium: yes
    """

    def test_npowatchlist_lookup(self, execute_task):
        """npo_watchlist: Test npo watchlist lookup (ONLINE)."""
        task = execute_task('test')
        entry = task.find_entry(
            url='https://www.npostart.nl/hollands-hoop/08-02-2020/BV_101396963'
        )  # a premium serie
        assert entry['npo_id'] == 'BV_101396963'
        assert entry['npo_url'] == 'https://www.npostart.nl/hollands-hoop/BV_101385153'
        assert entry['npo_name'] == 'Hollands Hoop'
        assert entry['npo_runtime'] == '53'
        assert entry['npo_premium'] is True


@pytest.mark.online
@pytest.mark.xdist_group(name="npo_watchlist")
class TestNpoWatchlistLanguageTheTVDBLookup:
    config = """
        tasks:
          test:
            npo_watchlist:
              email: '8h3ga3+7nzf7xueal70o@sharklasers.com'
              password: 'Fl3xg3t!'
            thetvdb_lookup: yes
    """

    def test_tvdblang_lookup(self, execute_task):
        """npo_watchlist: Test npo_watchlist tvdb language lookup (ONLINE)."""
        task = execute_task('test')

        entry = task.find_entry(
            url='https://www.npostart.nl/zondag-met-lubach/09-11-2014/VPWON_1220631'
        )  # s01e01
        assert entry['npo_language'] == 'nl'
        assert entry['language'] == 'nl'
        assert entry['tvdb_id'] == 288799
        assert entry['tvdb_language'] == 'nl'
