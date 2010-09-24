import os
from tests import FlexGetBase
import shutil


class TestInputCache(FlexGetBase):

    __yaml__ = """
        feeds:
          test_1:
            rss:
              url: tests/cached.xml
          test_2:
            rss:
              url: tests/cached.xml
    """

    def setup(self):
        FlexGetBase.setup(self)
        shutil.copy('tests/rss.xml', 'tests/cached.xml')

    def teardown(self):
        if os.path.exists('tests/cached.xml'):
            os.remove('tests/cached.xml')

    def test_cache(self):
        """Test input caching"""
        self.execute_feed('test_1')
        assert self.feed.entries, 'should have created entries at the start'
        os.remove('tests/cached.xml')
        f = open('tests/cached.xml', 'w')
        f.write('')
        f.close()
        self.execute_feed('test_2')
        assert self.feed.entries, 'should have created entries from the cache'
