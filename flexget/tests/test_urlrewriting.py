import pytest

from flexget.plugin import get_plugin_by_name


class TestURLRewriters:
    """
    Bad example, does things manually, you should use task.find_entry to check existance
    """

    config = """
        tasks:
          test:
            # make test data
            mock:
              - {title: 'tpb page', url: 'https://thepiratebay.org/description.php?id=8492471'}
              - {title: 'tbp search', url: 'https://thepiratebay.org/search.php?q=something'}
              - {title: 'tbp torrent', url: 'https://torrents.thepiratebay.org/8492471/Test.torrent'}
              - {title: 'tbp apibay', url: 'https://apibay.org/description.php?id=8492471'}
              - {title: 'tbp torrent bad subdomain', url: 'https://torrent.thepiratebay.org/description.php?id=8492471'}
              - {title: 'nyaa', url: 'https://www.nyaa.si/view/15'}
              - {title: 'cinemageddon download', url: 'http://cinemageddon.net/details.php?id=1234'}
              - {title: 'rutracker_topic', url: 'https://rutracker.org/forum/viewtopic.php?t=2455223'}
              - {title: 'ettv page', url: 'https://www.ettvcentral.com/torrent/1239122/build-a-scraper-software-using-python'}
    """

    def get_urlrewriter(self, name):
        info = get_plugin_by_name(name)
        return info.instance

    def test_piratebay(self, execute_task):
        task = execute_task('test')
        # test with piratebay entry
        urlrewriter = self.get_urlrewriter('piratebay')
        entry = task.find_entry(title='tpb page')
        assert urlrewriter.url_rewritable(task, entry)
        entry = task.find_entry(title='tbp torrent')
        assert not urlrewriter.url_rewritable(task, entry), (
            'TPB direct torrent link should not be url_rewritable'
        )
        entry = task.find_entry(title='tbp apibay')
        assert urlrewriter.url_rewritable(task, entry)
        entry = task.find_entry(title='tbp torrent bad subdomain')
        assert not urlrewriter.url_rewritable(task, entry), (
            'TPB link with invalid subdomain should not be url_rewritable'
        )

    def test_piratebay_search(self, execute_task):
        task = execute_task('test')
        # test with piratebay entry
        urlrewriter = self.get_urlrewriter('piratebay')
        entry = task.find_entry(title='tbp search')
        assert urlrewriter.url_rewritable(task, entry)

    def test_nyaa_torrents(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='nyaa')
        urlrewriter = self.get_urlrewriter('nyaa')
        assert entry['url'] == 'https://www.nyaa.si/view/15'
        assert urlrewriter.url_rewritable(task, entry)
        urlrewriter.url_rewrite(task, entry)
        assert entry['url'] == 'https://www.nyaa.si/download/15.torrent'

    def test_cinemageddon(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='cinemageddon download')
        urlrewriter = self.get_urlrewriter('cinemageddon')
        assert urlrewriter.url_rewritable(task, entry)
        urlrewriter.url_rewrite(task, entry)
        assert (
            entry['url']
            == 'http://cinemageddon.net/download.php?id=1234&name=cinemageddon%20download.torrent'
        )

    @pytest.mark.online
    def test_rutracker(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='rutracker_topic')
        urlrewriter = self.get_urlrewriter('rutracker')
        assert urlrewriter.url_rewritable(task, entry)
        urlrewriter.url_rewrite(task, entry)
        assert (
            entry['url']
            == 'magnet:?xt=urn:btih:38527C88CFE76411EF0C20FDF36B84DFE2C2D210&tr=http:%2F%2Fbt.t-ru.org%2Fann%3Fmagnet&tr=http:%2F%2Fbt2.t-ru.org%2Fann%3Fmagnet&tr=http:%2F%2Fbt3.t-ru.org%2Fann%3Fmagnet&tr=http:%2F%2Fbt4.t-ru.org%2Fann%3Fmagnet&dn=%D0%9F%D0%A0%D0%AB%D0%96%D0%9A%D0%98+%D0%9D%D0%90+%D0%9B%D0%AB%D0%96%D0%90%D0%A5+%D0%A1+%D0%A2%D0%A0%D0%90%D0%9C%D0%9F%D0%9B%D0%98%D0%9D%D0%90.+%D0%A1%D0%B5%D0%B7%D0%BE%D0%BD+2008-2009.+%D0%92%D0%A1%D0%95+%D0%A1%D0%9E%D0%A0%D0%95%D0%92%D0%9D%D0%9E%D0%92%D0%90%D0%9D%D0%98%D0%AF.+%D0%A1+%D1%80%D0%B0%D0%B7%D0%BD%D1%8B%D1%85+%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB%D0%BE%D0%B2.%5B%D0%A1%D0%B5%D0%B7%D0%BE%D0%BD+2008-2009%2C+%D1%80%D0%B0%D0%B7%D0%BD%D0%BE%D0%B3%D0%BE+%D0%BA%D0%B0%D1%87%D0%B5%D1%81%D1%82%D0%B2%D0%B0.%5D'
        )

    @pytest.mark.online
    def test_ettv(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='ettv page')
        urlrewriter = self.get_urlrewriter('ettv')
        assert urlrewriter.url_rewritable(task, entry)
        urlrewriter.url_rewrite(task, entry)
        assert (
            entry['url']
            == 'magnet:?xt=urn:btih:cf479cde41a2a8c4a65cf963025b525f18932bdc&dn=Build+a+Scraper+Software+Using+Python&xl=2109955281&tr=udp%3A%2F%2Fopen.stealth.si:80/announce&tr=udp%3A%2F%2Ftracker.tiny-vps.com:6969/announce&tr=udp%3A%2F%2Ffasttracker.foreverpirates.co:6969/announce&tr=udp%3A%2F%2Ftracker.opentrackr.org:1337/announce&tr=udp%3A%2F%2Fexplodie.org:6969/announce&tr=udp%3A%2F%2Ftracker.cyberia.is:6969/announce&tr=udp%3A%2F%2Fipv4.tracker.harry.lu:80/announce&tr=udp%3A%2F%2Ftracker.uw0.xyz:6969/announce&tr=udp%3A%2F%2Fopentracker.i2p.rocks:6969/announce&tr=udp%3A%2F%2Ftracker.birkenwald.de:6969/announce&tr=udp%3A%2F%2Ftracker.torrent.eu.org:451/announce&tr=udp%3A%2F%2Ftracker.moeking.me:6969/announce&tr=udp%3A%2F%2Ftracker.dler.org:6969/announce&tr=udp%3A%2F%2F9.rarbg.me:2970/announce'
        )


class TestRegexpurlrewriter:
    # TODO: this test is broken?

    config = r"""
        tasks:
          test:
            mock:
              - {title: 'irrelevant', url: 'http://newzleech.com/?p=123'}
            accept_all: yes
            urlrewrite:
              newzleech:
                regexp: 'http://newzleech.com/\?p=(?P<id>\d+)'
                format: 'http://newzleech.com/?m=gen&dl=1&post=\g<id>'
    """

    def test_newzleech(self, execute_task):
        task = execute_task('test')
        assert task.find_entry(url='http://newzleech.com/?m=gen&dl=1&post=123'), (
            'did not url_rewrite properly'
        )
