from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.tools import assert_true
from flexget.plugin import get_plugin_by_name


class TestURLRewriters(FlexGetBase):
    """
        Bad example, does things manually, you should use task.find_entry to check existance
    """

    __yaml__ = """
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
              - {title: 'isohunt search', url: 'http://isohunt.com/torrents/?ihq=Query.Here'}
              - {title: 'isohunt direct', url: 'http://isohunt.com/torrent_details/123456789/Name.Here'}
    """

    def setup(self):
        FlexGetBase.setup(self)
        self.execute_task('test')

    def get_urlrewriter(self, name):
        info = get_plugin_by_name(name)
        return info.instance

    def test_piratebay(self):
        # test with piratebay entry
        urlrewriter = self.get_urlrewriter('piratebay')
        entry = self.task.find_entry(title='tpb page')
        assert_true(urlrewriter.url_rewritable(self.task, entry))
        entry = self.task.find_entry(title='tbp torrent')
        assert not urlrewriter.url_rewritable(self.task, entry), \
            'TPB direct torrent link should not be url_rewritable'
        entry = self.task.find_entry(title='tbp torrent subdomain')
        assert_true(urlrewriter.url_rewritable(self.task, entry))
        entry = self.task.find_entry(title='tbp torrent bad subdomain')
        assert not urlrewriter.url_rewritable(self.task, entry), \
            'TPB link with invalid subdomain should not be url_rewritable'

    def test_piratebay_search(self):
        # test with piratebay entry
        urlrewriter = self.get_urlrewriter('piratebay')
        entry = self.task.find_entry(title='tbp search')
        assert_true(urlrewriter.url_rewritable(self.task, entry))

    def test_nyaa_torrents(self):
        entry = self.task.find_entry(title='nyaa')
        urlrewriter = self.get_urlrewriter('nyaa')
        assert entry['url'] == 'http://www.nyaa.eu/?page=torrentinfo&tid=12345'
        assert_true(urlrewriter.url_rewritable(self.task, entry))
        urlrewriter.url_rewrite(self.task, entry)
        assert entry['url'] == 'http://www.nyaa.eu/?page=download&tid=12345'

    def test_isohunt(self):
        entry = self.task.find_entry(title='isohunt search')
        urlrewriter = self.get_urlrewriter('isohunt')
        assert not urlrewriter.url_rewritable(self.task, entry), \
            'search entry should not be url_rewritable'
        entry = self.task.find_entry(title='isohunt direct')
        assert urlrewriter.url_rewritable(self.task, entry), \
            'direct entry should be url_rewritable'


class TestRegexpurlrewriter(FlexGetBase):
    # TODO: this test is broken?

    __yaml__ = """
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

    def test_newzleech(self):
        self.execute_task('test')
        assert self.task.find_entry(url='http://newzleech.com/?m=gen&dl=1&post=123'), \
            'did not url_rewrite properly'
