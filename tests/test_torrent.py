import os

from tests import FlexGetBase, with_filecopy
from flexget.utils.bittorrent import Torrent 


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
              - {title: 'test_magnet'}
            set:
              url: 'magnet:?xt=urn:btih:HASH&dn=title'
            add_trackers:
              - udp://thetracker.com/announce

          test_remove_trackers:
            mock:
              - {title: 'test', file: 'test_remove_trackers.torrent'}
              - title: 'test_magnet'
            set:
              url: 'magnet:?xt=urn:btih:HASH&dn=title&tr=http://torrent.ubuntu.com:6969/announce'
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
        # Check magnet url
        assert 'tr=udp://thetracker.com/announce' in self.feed.find_entry(title='test_magnet')['url']

    @with_filecopy('test.torrent', 'test_remove_trackers.torrent')
    def test_remove_trackers(self):
        self.execute_feed('test_remove_trackers')
        torrent = self.load_torrent('test_remove_trackers.torrent')
        assert 'http://torrent.ubuntu.com:6969/announce' not in torrent.get_multitrackers(), \
            'ubuntu tracker should have been removed'
        # Check magnet url
        assert 'tr=http://torrent.ubuntu.com:6969/announce' not in self.feed.find_entry(title='test_magnet')['url']


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


class TestTorrentScrub(FlexGetBase):

    __yaml__ = """
        feeds:
          test_all:
            mock:
              - {title: 'test', file: 'tmp/test.torrent'}
              - {title: 'LICENSE', file: 'tmp/LICENSE.torrent'}
              - {title: 'LICENSE-resume', file: 'tmp/LICENSE-resume.torrent'}
            accept_all: yes
            torrent_scrub: all

          test_fields:
            mock:
              - {title: 'LICENSE', file: 'tmp/LICENSE.torrent'}
            accept_all: yes
            torrent_scrub:
              - comment
              - info.x_cross_seed
              - field.that.never.exists

          test_off:
            mock:
              - {title: 'LICENSE-resume', file: 'tmp/LICENSE-resume.torrent'}
            accept_all: yes
            torrent_scrub: off
    """

    filenames = (
        (True, 'test.torrent'), 
        (False, 'LICENSE.torrent'), 
        (False, 'LICENSE-resume.torrent'),
    )

    @with_filecopy("*.torrent", "tmp/")
    def test_torrent_scrub(self):
        # Run feed        
        self.execute_feed('test_all')

        for clean, filename in self.filenames: 
            original = Torrent.from_file(filename)
            modified = self.feed.find_entry(title=os.path.splitext(filename)[0])['torrent']
            osize = os.path.getsize(filename)
            msize = os.path.getsize("tmp/" + filename)

            # Dump small torrents on demand
            if 0 and not clean:
                print "original=%r" % original.content
                print "modified=%r" % modified.content

            # Make sure essentials survived
            assert 'announce' in modified.content
            assert 'info' in modified.content
            assert 'name' in modified.content['info']  
            assert 'piece length' in modified.content['info']  
            assert 'pieces' in modified.content['info']  

            # Check that hashes have changed accordingly
            if clean:
                assert osize == msize, "Filesizes aren't supposed to differ!"
                assert original.get_info_hash() == modified.get_info_hash(), 'info dict changed in ' + filename
            else:
                assert osize > msize, "Filesizes must be different!"
                assert original.get_info_hash() != modified.get_info_hash(), filename + " wasn't scrubbed!"  

            # Check essential keys were scrubbed
            if filename == 'LICENSE.torrent':
                assert 'x_cross_seed' in original.content['info']  
                assert 'x_cross_seed' not in modified.content['info']

            if filename == 'LICENSE-resume.torrent':
                assert 'libtorrent_resume' in original.content  
                assert 'libtorrent_resume' not in modified.content

    @with_filecopy("*.torrent", "tmp/")
    def test_torrent_scrub_fields(self):
        self.execute_feed('test_fields')
        torrent = self.feed.find_entry(title='LICENSE')['torrent']
        assert 'name' in torrent.content['info'], "'info.name' was lost"
        assert 'comment' not in torrent.content, "'comment' not scrubbed"
        assert 'x_cross_seed' not in torrent.content['info'], "'info.x_cross_seed' not scrubbed"

    @with_filecopy("*.torrent", "tmp/")
    def test_torrent_scrub_off(self):
        self.execute_feed('test_off')

        for clean, filename in self.filenames: 
            osize = os.path.getsize(filename)
            msize = os.path.getsize("tmp/" + filename)
            assert osize == msize, "Filesizes aren't supposed to differ (%r %d, %r %d)!" % (
                filename, osize, "tmp/" + filename, msize)
