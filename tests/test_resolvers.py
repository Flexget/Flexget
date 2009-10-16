from tests import FlexGetBase
from nose.tools import assert_true, assert_false
from flexget.plugin import get_plugin_by_name

class TestResolvers(FlexGetBase):
    """
        Bad example, does things manually, you should use feed.find_entry to check existance
    """
    __yaml__ = """
        feeds:
          test:
            # make test data
            input_mock:
              - {title: 'something', url: 'http://thepiratebay.org/tor/8492471/Test.avi'}
              - {title: 'bar', url: 'http://thepiratebay.org/search/something'}
              - {title: 'nyaa', url: 'http://www.nyaatorrents.org/?page=torrentinfo&tid=12345'}
              - {title: 'isohunt search', url: 'http://isohunt.com/torrents/?ihq=Query.Here'}
              - {title: 'isohunt direct', url: 'http://isohunt.com/torrent_details/123456789/Name.Here'}
    """
    def setup(self):
        FlexGetBase.setUp(self)
        self.execute_feed('test')

    def get_resolver(self, name):
        info = get_plugin_by_name(name)
        return info.instance

    def test_piratebay(self):
        # test with piratebay entry
        resolver = self.get_resolver('piratebay')
        entry = self.feed.entries[0]
        assert_true(resolver.resolvable(self.feed, entry))

    def test_piratebay_search(self):
        # test with piratebay entry
        resolver = self.get_resolver('piratebay')
        entry = self.feed.entries[1]
        assert_true(resolver.resolvable(self.feed, entry))

    def test_nyaa_torrents(self):
        entry = self.feed.entries[2]
        resolver = self.get_resolver('nyaatorrents')
        assert entry['url'] == 'http://www.nyaatorrents.org/?page=torrentinfo&tid=12345'
        assert_true(resolver.resolvable(self.feed, entry))
        resolver.resolve(self.feed, entry)
        assert entry['url'] == 'http://www.nyaatorrents.org/?page=download&tid=12345'

    def test_isohunt(self):
        entry = self.feed.find_entry(title='isohunt search')
        resolver = self.get_resolver('isohunt')
        assert not resolver.resolvable(self.feed, entry), \
            'search entry should not be resolvable'
        entry = self.feed.find_entry(title='isohunt direct')
        assert resolver.resolvable(self.feed, entry), \
            'direct entry should be resolvable'

class TestRegexpResolver(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'irrelevant', url: 'http://newzleech.com/?p=123'}
            regexp_resolve:
              newzleech:
                match: http://newzleech.com/?p=
                replace: http://newzleech.com/?m=gen&dl=1&post=
    """

    def test_newzleech(self):
        self.execute_feed('test')
        assert not self.feed.find_entry(url='http://newzleech.com/?m=gen&dl=1&post=123'), 'did not resolve properly'
