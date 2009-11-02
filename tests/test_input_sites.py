from tests import FlexGetBase
from nose.plugins.attrib import attr

class TestRlsLog(FlexGetBase):

    __yaml__ = """
        feeds:
          test_rlslog:
            rlslog: http://www.rlslog.net/category/movies/dvdrip/
          test_scenereleases:
            scenereleases: http://scenereleases.info/category/movies/movies-dvd-rip
    """

    @attr(online=True)
    def test_rlslog(self):
        self.execute_feed('test_rlslog')
        assert self.feed.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_scenereleases(self):
        self.execute_feed('test_scenereleases')
        assert self.feed.entries, 'no entries created / site may be down'

