from tests import FlexGetBase


class TestMetainfo(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test_quality:
            mock:
              - {title: 'test quality', description: 'metainfo quality should parse quality 720p from this'}
          test_content_size:
            mock:
              - {title: 'size 200MB', description: 'metainfo content size should parse size 200MB from this'}
              - {title: 'size 1024MB', description: 'metainfo content size should parse size 1.0GB from this'}
    """
    
    def test_quality(self):
        """Metainfo: parse quality"""
        self.execute_feed('test_quality')
        assert self.feed.find_entry(quality='720p'), 'Quality not parsed'
        
    def test_content_size(self):
        """Metainfo: parse content size"""
        self.execute_feed('test_content_size')
        assert self.feed.find_entry(content_size=200), 'Content size 200 MB absent'
        assert self.feed.find_entry(content_size=1024), 'Content size 1024 MB absent'
