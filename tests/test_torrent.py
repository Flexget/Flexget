import shutil
from tests import FlexGetBase


class TestInfoHash(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'test', file: 'tests/test.torrent'}
    """

    def test_infohash(self):
        """Torrent: infohash parsing"""
        self.execute_feed('test')
        assert self.feed.entries[0]['torrent_info_hash'] == '20AE692114DC343C86DF5B07C276E5077E581766', \
            'InfoHash does not match'
