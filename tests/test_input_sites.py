from tests import FlexGetBase
from nose.plugins.attrib import attr

class TestRlsLog(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            rlslog: http://www.rlslog.net/category/movies/dvdrip/
    """

    @attr(online=True)
    def test_parsing(self):
        self.execute_feed('test')
        assert self.feed.entries, 'no entries created'

class TestScenereleases(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            scenereleases: http://scenereleases.info/category/movies/movies-dvd-rip
    """

    @attr(online=True)
    def test_parsing(self):
        self.execute_feed('test')
        assert self.feed.entries, 'no entries created'

