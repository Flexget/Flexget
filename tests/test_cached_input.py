import os
from tests import FlexGetBase, with_filecopy


class TestInputCache(FlexGetBase):

    __yaml__ = """
        feeds:
          test_1:
            rss:
              url: cached.xml
          test_2:
            rss:
              url: cached.xml
    """

    @with_filecopy('rss.xml', 'cached.xml')
    def test_cache(self):
        """Test input caching"""
        # Don't use execute_feed in this test as it runs process_start (which clears the cache) before each feed
        self.manager.create_feeds()
        self.manager.process_start()
        feed = self.manager.feeds['test_1']
        feed.execute()
        assert feed.entries, 'should have created entries at the start'
        os.remove('cached.xml')
        f = open('cached.xml', 'w')
        f.write('')
        f.close()
        feed = self.manager.feeds['test_2']
        feed.execute()
        assert feed.entries, 'should have created entries from the cache'
        self.manager.process_end()
