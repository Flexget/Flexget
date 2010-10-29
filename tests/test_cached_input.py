import os
from tests import FlexGetBase, with_filecopy


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

    @with_filecopy('tests/rss.xml', 'tests/cached.xml')
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
