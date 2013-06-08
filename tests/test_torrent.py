from __future__ import unicode_literals, division, absolute_import
import os

from nose.plugins.attrib import attr
from tests import FlexGetBase, with_filecopy
from flexget.utils.bittorrent import Torrent


class TestInfoHash(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'test', file: 'test.torrent'}
            accept_all: yes
    """

    def test_infohash(self):
        """Torrent: infohash parsing"""
        self.execute_task('test')
        info_hash = self.task.entries[0].get('torrent_info_hash')
        assert info_hash == '14FFE5DD23188FD5CB53A1D47F1289DB70ABF31E', \
            'InfoHash does not match (got %s)' % info_hash


class TestSeenInfoHash(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: test, file: test.torrent}
            accept_all: yes
          test2:
            mock:
              - {title: test2, file: test2.torrent}
            accept_all: yes
          test_same_run:
            mock:
              - {title: test, torrent_info_hash: 20AE692114DC343C86DF5B07C276E5077E581766}
              - {title: test2, torrent_info_hash: 20ae692114dc343c86df5b07c276e5077e581766}
            accept_all: yes
    """

    @with_filecopy('test.torrent', 'test2.torrent')
    def test_seen_info_hash(self):
        self.execute_task('test')
        assert self.task.find_entry('accepted', title='test'), 'torrent should have been accepted on first run'
        self.execute_task('test2')
        assert self.task.find_entry('rejected', title='test2'), 'torrent should have been rejected on second run'

    def test_same_run(self):
        # Test that 2 entries with the same info hash don't get accepted on the same run.
        # Also tests that the plugin compares info hash case insensitively.
        self.execute_task('test_same_run')
        assert len(self.task.accepted) == 1, 'Should not have accepted both entries with the same info hash'


class TestModifyTrackers(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            accept_all: yes
        tasks:
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
              url: 'magnet:?xt=urn:btih:HASH&dn=title&tr=http://ipv6.torrent.ubuntu.com:6969/announce'
            remove_trackers:
              - ipv6

          test_modify_trackers:
            mock:
              - {title: 'test', file: 'test_modify_trackers.torrent'}
            modify_trackers:
              - test:
                  from: ubuntu
                  to: replaced
    """

    def load_torrent(self, filename):
        with open(filename, 'rb') as f:
            data = f.read()
        return Torrent(data)

    @with_filecopy('test.torrent', 'test_add_trackers.torrent')
    def test_add_trackers(self):
        self.execute_task('test_add_trackers')
        torrent = self.load_torrent('test_add_trackers.torrent')
        assert 'udp://thetracker.com/announce' in torrent.trackers, \
            'udp://thetracker.com/announce should have been added to trackers'
        # Check magnet url
        assert 'tr=udp://thetracker.com/announce' in self.task.find_entry(title='test_magnet')['url']

    @with_filecopy('test.torrent', 'test_remove_trackers.torrent')
    def test_remove_trackers(self):
        self.execute_task('test_remove_trackers')
        torrent = self.load_torrent('test_remove_trackers.torrent')
        assert 'http://ipv6.torrent.ubuntu.com:6969/announce' not in torrent.trackers, \
            'ipv6 tracker should have been removed'

        # Check magnet url
        assert 'tr=http://ipv6.torrent.ubuntu.com:6969/announce' not in self.task.find_entry(title='test_magnet')['url']

    @with_filecopy('test.torrent', 'test_modify_trackers.torrent')
    def test_modify_trackers(self):
        self.execute_task('test_modify_trackers')
        torrent = self.load_torrent('test_modify_trackers.torrent')
        assert 'http://torrent.replaced.com:6969/announce' in torrent.trackers, \
            'ubuntu tracker should have been added'

        # TODO: due implementation this bugs! Torrent class needs to be fixed ...
        return
        assert 'http://torrent.ubuntu.com:6969/announce' not in torrent.trackers, \
            'ubuntu tracker should have been removed'


class TestPrivateTorrents(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'test_private', file: 'private.torrent'}
              - {title: 'test_public', file: 'test.torrent'}
            accept_all: yes
            private_torrents: no
    """

    def test_private_torrents(self):
        self.execute_task('test')
        assert self.task.find_entry('rejected', title='test_private'), 'did not reject private torrent'
        assert self.task.find_entry('accepted', title='test_public'), 'did not pass public torrent'


class TestTorrentScrub(FlexGetBase):

    __tmp__ = True
    __yaml__ = """
        tasks:
          test_all:
            mock:
              - {title: 'test', file: '__tmp__test.torrent'}
              - {title: 'LICENSE', file: '__tmp__LICENSE.torrent'}
              - {title: 'LICENSE-resume', file: '__tmp__LICENSE-resume.torrent'}
            accept_all: yes
            torrent_scrub: all
            disable_builtins: [seen_info_hash]

          test_fields:
            mock:
              - {title: 'fields.LICENSE', file: '__tmp__LICENSE.torrent'}
            accept_all: yes
            torrent_scrub:
              - comment
              - info.x_cross_seed
              - field.that.never.exists

          test_off:
            mock:
              - {title: 'off.LICENSE-resume', file: '__tmp__LICENSE-resume.torrent'}
            accept_all: yes
            torrent_scrub: off
    """

    test_cases = (
        (True, 'test.torrent'),
        (False, 'LICENSE.torrent'),
        (False, 'LICENSE-resume.torrent'),
    )
    test_files = [i[1] for i in test_cases]

    @with_filecopy(test_files, "__tmp__")
    def test_torrent_scrub(self):
        # Run task
        self.execute_task('test_all')

        for clean, filename in self.test_cases:
            original = Torrent.from_file(filename)
            title = os.path.splitext(filename)[0]

            modified = self.task.find_entry(title=title)
            assert modified, "%r cannot be found in %r" % (title, self.task)
            modified = modified.get('torrent')
            assert modified, "No 'torrent' key in %r" % (title,)

            osize = os.path.getsize(filename)
            msize = os.path.getsize(self.__tmp__ + filename)

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
                assert original.info_hash == modified.info_hash, 'info dict changed in ' + filename
            else:
                assert osize > msize, "Filesizes must be different!"
                assert original.info_hash != modified.info_hash, filename + " wasn't scrubbed!"

            # Check essential keys were scrubbed
            if filename == 'LICENSE.torrent':
                assert 'x_cross_seed' in original.content['info']
                assert 'x_cross_seed' not in modified.content['info']

            if filename == 'LICENSE-resume.torrent':
                assert 'libtorrent_resume' in original.content
                assert 'libtorrent_resume' not in modified.content

    @with_filecopy(test_files, "__tmp__")
    def test_torrent_scrub_fields(self):
        self.execute_task('test_fields')
        title = 'fields.LICENSE'
        torrent = self.task.find_entry(title=title)
        assert torrent, "%r cannot be found in %r" % (title, self.task)
        torrent = torrent.get('torrent')
        assert torrent, "No 'torrent' key in %r" % (title,)

        assert 'name' in torrent.content['info'], "'info.name' was lost"
        assert 'comment' not in torrent.content, "'comment' not scrubbed"
        assert 'x_cross_seed' not in torrent.content['info'], "'info.x_cross_seed' not scrubbed"

    @with_filecopy(test_files, "__tmp__")
    def test_torrent_scrub_off(self):
        self.execute_task('test_off')

        for filename in self.test_files:
            osize = os.path.getsize(filename)
            msize = os.path.getsize(self.__tmp__ + filename)
            assert osize == msize, "Filesizes aren't supposed to differ (%r %d, %r %d)!" % (
                filename, osize, self.__tmp__ + filename, msize)


class TestTorrentAlive(FlexGetBase):
    __yaml__ = """
        presets:
          global:
            accept_all: yes
        tasks:
          test_torrent_alive_fail:
            mock:
              - {title: 'test', file: 'test_torrent_alive.torrent', url: fake}
            torrent_alive: 100000
          test_torrent_alive_pass:
            mock:
              - {title: 'test', file: 'test_torrent_alive.torrent', url: fake}
            torrent_alive: 0
    """

    @attr(online=True)
    @with_filecopy('test.torrent', 'test_torrent_alive.torrent')
    def test_torrent_alive_fail(self):
        self.execute_task('test_torrent_alive_fail')
        assert not self.task.accepted, 'Torrent should not have met seed requirement.'
        assert self.task._rerun_count == 1, ('Task should have been rerun 1 time. Was rerun %s times.' %
                                             self.task._rerun_count)

        # Run it again to make sure remember_rejected prevents a rerun from occurring
        self.execute_task('test_torrent_alive_fail')
        assert not self.task.accepted, 'Torrent should have been rejected by remember_rejected.'
        assert self.task._rerun_count == 0, 'Task should not have been rerun.'

    @attr(online=True)
    @with_filecopy('test.torrent', 'test_torrent_alive.torrent')
    def test_torrent_alive_pass(self):
        self.execute_task('test_torrent_alive_pass')
        assert self.task.accepted
        assert self.task._rerun_count == 0, 'Torrent should have been accepted without rerun.'

    @attr(online=True)
    def test_torrent_alive_udp_invalid_port(self):
        from flexget.plugins.filter.torrent_alive import get_udp_seeds
        assert get_udp_seeds('udp://[2001::1]/announce','HASH') == 0
        assert get_udp_seeds('udp://[::1]/announce','HASH') == 0
        assert get_udp_seeds('udp://["2100::1"]:-1/announce', 'HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1/announce','HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1:-1/announce','HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1:PORT/announce','HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1:65536/announce','HASH') == 0

class TestRtorrentMagnet(FlexGetBase):
    __tmp__ = True
    __yaml__ = """
        tasks:
          test:
            mock:
              - title: 'test'
                url: 'magnet:?xt=urn:btih:HASH&dn=title&tr=http://torrent.ubuntu.com:6969/announce'
            rtorrent_magnet: __tmp__
            accept_all: yes
    """


    def test_rtorrent_magnet(self):
        self.execute_task('test')
        filename = 'meta-test.torrent'
        fullpath = os.path.join(self.__tmp__, filename)
        assert os.path.isfile(fullpath)
        with open(fullpath) as f:
            assert (f.read() ==
                    'd10:magnet-uri76:magnet:?xt=urn:btih:HASH&dn=title&tr=http://torrent.ubuntu.com:6969/announcee')
