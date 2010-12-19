from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestInputSites(FlexGetBase):

    __yaml__ = """
        feeds:
          test_rlslog:
            rlslog: http://www.rlslog.net/category/movies/dvdrip/
          test_scenereleases:
            scenereleases: http://scenereleases.info/category/movies/movies-dvd-rip
          test_apple_trailers:
              apple_trailers: '320'
    """

    @attr(online=True)
    def test_rlslog(self):
        self.execute_feed('test_rlslog')
        assert self.feed.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_scenereleases(self):
        self.execute_feed('test_scenereleases')
        assert self.feed.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_apple_trailers(self):
        self.execute_feed('test_apple_trailers')
        assert self.feed.entries, 'no entries created / site may be down'
