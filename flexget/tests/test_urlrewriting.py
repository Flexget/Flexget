from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.plugin import get_plugin_by_name


class TestURLRewriters(object):
    """
        Bad example, does things manually, you should use task.find_entry to check existance
    """

    config = """
        tasks:
          test:
            # make test data
            mock:
              - {title: 'tpb page', url: 'http://thepiratebay.org/tor/8492471/Test.avi'}
              - {title: 'tbp search', url: 'http://thepiratebay.com/search/something'}
              - {title: 'tbp torrent', url: 'http://torrents.thepiratebay.se/8492471/Test.torrent'}
              - {title: 'tbp torrent subdomain', url: 'http://torrents.thepiratebay.se/8492471/Test.avi'}
              - {title: 'tbp torrent bad subdomain', url: 'http://torrent.thepiratebay.se/8492471/Test.avi'}
              - {title: 'nyaa', url: 'http://www.nyaa.eu/?page=torrentinfo&tid=12345'}
              - {title: 'cinemageddon download', url: 'http://cinemageddon.net/details.php?id=1234'}
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
        assert not urlrewriter.url_rewritable(task, entry), \
            'TPB direct torrent link should not be url_rewritable'
        entry = task.find_entry(title='tbp torrent subdomain')
        assert urlrewriter.url_rewritable(task, entry)
        entry = task.find_entry(title='tbp torrent bad subdomain')
        assert not urlrewriter.url_rewritable(task, entry), \
            'TPB link with invalid subdomain should not be url_rewritable'

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
        assert entry['url'] == 'http://www.nyaa.eu/?page=torrentinfo&tid=12345'
        assert urlrewriter.url_rewritable(task, entry)
        urlrewriter.url_rewrite(task, entry)
        assert entry['url'] == 'http://www.nyaa.eu/?page=download&tid=12345'

    def test_cinemageddon(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='cinemageddon download')
        urlrewriter = self.get_urlrewriter('cinemageddon')
        assert urlrewriter.url_rewritable(task, entry)
        urlrewriter.url_rewrite(task, entry)
        assert entry['url'] == 'http://cinemageddon.net/download.php?id=1234&name=cinemageddon%20download.torrent'


class TestRegexpurlrewriter(object):
    # TODO: this test is broken?

    config = """
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
        assert task.find_entry(url='http://newzleech.com/?m=gen&dl=1&post=123'), \
            'did not url_rewrite properly'
