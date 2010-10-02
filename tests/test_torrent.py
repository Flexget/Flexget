import shutil
from tests import FlexGetBase
from flexget.plugins.modify_torrent import Torrent


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
        hash = self.feed.entries[0].get('torrent_info_hash')
        assert hash == '20AE692114DC343C86DF5B07C276E5077E581766', \
            'InfoHash does not match (got %s)' % hash


class TestModifyTrackers(FlexGetBase):

    __yaml__ = """
        feeds:
          test_add_trackers:
            mock:
              - {title: 'test', file: 'tests/test_add_trackers.torrent'}
            add_trackers:
              - udp://thetracker.com/announce

          test_remove_trackers:
            mock:
              - {title: 'test', file: 'tests/test_remove_trackers.torrent'}
            remove_trackers:
              - ubuntu
    """

    testfiles = ['tests/test_add_trackers.torrent', 'tests/test_remove_trackers.torrent']

    def setup(self):
        FlexGetBase.setup(self)
        for filename in self.testfiles:
            shutil.copy('tests/test.torrent', filename)

    def load_torrent(self, filename):
        f = open(filename, 'rb')
        data = f.read()
        f.close()
        return Torrent(data)

    def test_add_trackers(self):
        self.execute_feed('test_add_trackers')
        torrent = self.load_torrent('tests/test_add_trackers.torrent')
        assert 'udp://thetracker.com/announce' in torrent.get_multitrackers(), \
            'udp://thetracker.com/announce should have been added to trackers'

    def test_remove_trackers(self):
        self.execute_feed('test_remove_trackers')
        torrent = self.load_torrent('tests/test_remove_trackers.torrent')
        assert 'http://torrent.ubuntu.com:6969/announce' not in torrent.get_multitrackers(), \
            'ubuntu tracker should have been removed'
