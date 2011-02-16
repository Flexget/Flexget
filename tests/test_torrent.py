from tests import FlexGetBase, with_filecopy
from flexget.plugins.modify_torrent import Torrent


class TestInfoHash(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'test', file: 'test.torrent'}
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
              - {title: 'test', file: 'test_add_trackers.torrent'}
            add_trackers:
              - udp://thetracker.com/announce

          test_remove_trackers:
            mock:
              - {title: 'test', file: 'test_remove_trackers.torrent'}
            remove_trackers:
              - ubuntu
    """

    def load_torrent(self, filename):
        f = open(filename, 'rb')
        data = f.read()
        f.close()
        return Torrent(data)

    @with_filecopy('test.torrent', 'test_add_trackers.torrent')
    def test_add_trackers(self):
        self.execute_feed('test_add_trackers')
        torrent = self.load_torrent('test_add_trackers.torrent')
        assert 'udp://thetracker.com/announce' in torrent.get_multitrackers(), \
            'udp://thetracker.com/announce should have been added to trackers'

    @with_filecopy('test.torrent', 'test_remove_trackers.torrent')
    def test_remove_trackers(self):
        self.execute_feed('test_remove_trackers')
        torrent = self.load_torrent('test_remove_trackers.torrent')
        assert 'http://torrent.ubuntu.com:6969/announce' not in torrent.get_multitrackers(), \
            'ubuntu tracker should have been removed'


class TestPrivateTorrents(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'test_private', file: 'private.torrent'}
              - {title: 'test_public', file: 'test.torrent'}
            accept_all: yes
            private_torrents: no
    """
    
    def test_private_torrents(self):
        self.execute_feed('test')
        assert self.feed.find_entry('rejected', title='test_private'), 'did not reject private torrent'
        assert self.feed.find_entry('accepted', title='test_public'), 'did not pass public torrent'
