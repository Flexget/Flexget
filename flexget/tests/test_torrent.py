import os
from unittest import mock

import pytest

from flexget.utils.bittorrent import Torrent


class TestInfoHash:
    config = """
        tasks:
          test:
            mock:
              - {title: 'test', file: 'test.torrent'}
            accept_all: yes
          test_magnet:
            mock:
              - title: test magnet
                url: magnet:?xt=urn:btih:2a8959bed2be495bb0e3ea96f497d873d5faed05&dn=some.thing.720p
              - title: test magnet with base16
                urls: ['magnet:?xt=urn:btih:2b3959bed2be445bb0e3ea96f497d873d5faed05&dn=some.thing.else.720p']
              - title: test magnet with base32
                urls: ['magnet:?xt=urn:btih:WRN7ZT6NKMA6SSXYKAFRUGDDIFJUNKI2&dn=some.thing.else.720p']
    """

    def test_infohash(self, execute_task):
        """Torrent: infohash parsing"""
        task = execute_task('test')
        info_hash = task.entries[0].get('torrent_info_hash')
        assert info_hash == '14FFE5DD23188FD5CB53A1D47F1289DB70ABF31E', (
            f'InfoHash does not match (got {info_hash})'
        )

    def test_magnet_infohash(self, execute_task):
        """Tests metainfo/magnet_btih plugin"""
        task = execute_task('test_magnet')
        assert (
            task.all_entries[0]['torrent_info_hash'] == '2A8959BED2BE495BB0E3EA96F497D873D5FAED05'
        )
        assert (
            task.all_entries[1]['torrent_info_hash'] == '2B3959BED2BE445BB0E3EA96F497D873D5FAED05'
        )
        assert (
            task.all_entries[2]['torrent_info_hash'] == 'B45BFCCFCD5301E94AF8500B1A1863415346A91A'
        )


class TestSeenInfoHash:
    config = """
        tasks:
          test:
            mock:
              - {title: test, file: '__tmp__/test.torrent'}
            accept_all: yes
          test2:
            mock:
              - {title: test2, file: '__tmp__/test.torrent'}
            accept_all: yes
          test_same_run:
            mock:
              - {title: test, torrent_info_hash: 20AE692114DC343C86DF5B07C276E5077E581766}
              - {title: test2, torrent_info_hash: 20ae692114dc343c86df5b07c276e5077e581766}
            accept_all: yes
    """

    @pytest.mark.filecopy('test.torrent', '__tmp__/test.torrent')
    def test_seen_info_hash(self, execute_task):
        task = execute_task('test')
        assert task.find_entry('accepted', title='test'), (
            'torrent should have been accepted on first run'
        )
        task = execute_task('test2')
        assert task.find_entry('rejected', title='test2'), (
            'torrent should have been rejected on second run'
        )

    def test_same_run(self, execute_task):
        # Test that 2 entries with the same info hash don't get accepted on the same run.
        # Also tests that the plugin compares info hash case insensitively.
        task = execute_task('test_same_run')
        assert len(task.accepted) == 1, (
            'Should not have accepted both entries with the same info hash'
        )


class TestModifyTrackers:
    config = """
        templates:
          global:
            accept_all: yes
        tasks:
          test_add_trackers:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
              - {title: 'test_magnet'}
            set:
              url: 'magnet:?xt=urn:btih:HASH&dn=title'
            add_trackers:
              - udp://thetracker.com/announce

          test_remove_trackers:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
              - title: 'test_magnet'
            set:
              url: 'magnet:?xt=urn:btih:HASH&dn=title&tr=http://ipv6.torrent.ubuntu.com:6969/announce'
            remove_trackers:
              - ipv6

          test_modify_trackers:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
            modify_trackers:
              - test:
                  from: ubuntu
                  to: replaced
    """

    def load_torrent(self, filename):
        with open(filename, 'rb') as f:
            data = f.read()
        return Torrent(data)

    @pytest.mark.filecopy('test.torrent', '__tmp__/test.torrent')
    def test_add_trackers(self, execute_task, tmp_path):
        task = execute_task('test_add_trackers')
        torrent = self.load_torrent(os.path.join(tmp_path.as_posix(), 'test.torrent'))
        assert 'udp://thetracker.com/announce' in torrent.trackers, (
            'udp://thetracker.com/announce should have been added to trackers'
        )
        # Check magnet url
        assert 'tr=udp://thetracker.com/announce' in task.find_entry(title='test_magnet')['url']

    @pytest.mark.filecopy('test.torrent', '__tmp__/test.torrent')
    def test_remove_trackers(self, execute_task, tmp_path):
        task = execute_task('test_remove_trackers')
        torrent = self.load_torrent(os.path.join(tmp_path.as_posix(), 'test.torrent'))
        assert 'http://ipv6.torrent.ubuntu.com:6969/announce' not in torrent.trackers, (
            'ipv6 tracker should have been removed'
        )

        # Check magnet url
        assert (
            'tr=http://ipv6.torrent.ubuntu.com:6969/announce'
            not in task.find_entry(title='test_magnet')['url']
        )

    @pytest.mark.filecopy('test.torrent', '__tmp__/test.torrent')
    def test_modify_trackers(self, execute_task, tmp_path):
        execute_task('test_modify_trackers')
        torrent = self.load_torrent(tmp_path.joinpath('test.torrent'))
        assert 'http://torrent.replaced.com:6969/announce' in torrent.trackers, (
            'ubuntu tracker should have been added'
        )


class TestPrivateTorrents:
    config = """
        tasks:
          test:
            mock:
              - {title: 'test_private', file: 'private.torrent'}
              - {title: 'test_public', file: 'test.torrent'}
            accept_all: yes
            private_torrents: no
    """

    def test_private_torrents(self, execute_task):
        task = execute_task('test')
        assert task.find_entry('rejected', title='test_private'), 'did not reject private torrent'
        assert task.find_entry('accepted', title='test_public'), 'did not pass public torrent'


class TestTorrentScrub:
    config = """
        tasks:
          test_all:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent'}
              - {title: 'LICENSE', file: '__tmp__/LICENSE.torrent'}
              - {title: 'LICENSE-resume', file: '__tmp__/LICENSE-resume.torrent'}
            accept_all: yes
            torrent_scrub: all
            disable: [seen_info_hash]

          test_fields:
            mock:
              - {title: 'fields.LICENSE', file: '__tmp__/LICENSE.torrent'}
            accept_all: yes
            torrent_scrub:
              - comment
              - info.x_cross_seed
              - field.that.never.exists

          test_off:
            mock:
              - {title: 'off.LICENSE-resume', file: '__tmp__/LICENSE-resume.torrent'}
            accept_all: yes
            torrent_scrub: off
    """

    test_cases = (
        (True, 'test.torrent'),
        (False, 'LICENSE.torrent'),
        (False, 'LICENSE-resume.torrent'),
    )
    test_files = [i[1] for i in test_cases]

    @pytest.mark.filecopy(test_files, '__tmp__')
    def test_torrent_scrub(self, execute_task, tmp_path):
        # Run task
        task = execute_task('test_all')

        for clean, filename in self.test_cases:
            original = Torrent.from_file(filename)
            title = os.path.splitext(filename)[0]

            modified = task.find_entry(title=title)
            assert modified, f"{title!r} cannot be found in {task!r}"
            modified = modified.get('torrent')
            assert modified, f"No 'torrent' key in {title!r}"

            osize = os.path.getsize(filename)
            msize = tmp_path.joinpath(filename).stat().st_size

            # Dump small torrents on demand
            if False:
                print(f"original={original.content!r}")
                print(f"modified={modified.content!r}")

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

    @pytest.mark.filecopy(test_files, '__tmp__')
    def test_torrent_scrub_fields(self, execute_task):
        task = execute_task('test_fields')
        title = 'fields.LICENSE'
        torrent = task.find_entry(title=title)
        assert torrent, f"{title!r} cannot be found in {task!r}"
        torrent = torrent.get('torrent')
        assert torrent, f"No 'torrent' key in {title!r}"

        assert 'name' in torrent.content['info'], "'info.name' was lost"
        assert 'comment' not in torrent.content, "'comment' not scrubbed"
        assert 'x_cross_seed' not in torrent.content['info'], "'info.x_cross_seed' not scrubbed"

    @pytest.mark.filecopy(test_files, '__tmp__')
    def test_torrent_scrub_off(self, execute_task, tmp_path):
        execute_task('test_off')

        for filename in self.test_files:
            osize = os.path.getsize(filename)
            msize = tmp_path.joinpath(filename).stat().st_size
            assert osize == msize, (
                f"Filesizes aren't supposed to differ ({filename!r} {osize}, {self.__tmp__ + filename!r} {msize})!"
            )


class TestTorrentAlive:
    config = """
        templates:
          global:
            accept_all: yes
        tasks:
          test_torrent_alive_fail:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent', url: fake}
            torrent_alive: 100000
          test_torrent_alive_pass:
            mock:
              - {title: 'test', file: '__tmp__/test.torrent', url: fake}
            torrent_alive: 0
    """

    @pytest.mark.filecopy('test.torrent', '__tmp__/test.torrent')
    @mock.patch('flexget.utils.requests.get')
    def test_torrent_alive_fail(self, mocked_request, execute_task):
        task = execute_task('test_torrent_alive_fail')
        assert not task.accepted, 'Torrent should not have met seed requirement.'
        assert task._rerun_count == 1, (
            f'Task should have been rerun 1 time. Was rerun {task._rerun_count} times.'
        )

        # Run it again to make sure remember_rejected prevents a rerun from occurring
        task = execute_task('test_torrent_alive_fail')
        assert not task.accepted, 'Torrent should have been rejected by remember_rejected.'
        assert task._rerun_count == 0, 'Task should not have been rerun.'

    @pytest.mark.filecopy('test.torrent', '__tmp__/test.torrent')
    def test_torrent_alive_pass(self, execute_task):
        task = execute_task('test_torrent_alive_pass')
        assert task.accepted
        assert task._rerun_count == 0, 'Torrent should have been accepted without rerun.'

    def test_torrent_alive_udp_invalid_port(self):
        from flexget.components.bittorrent.torrent_alive import get_udp_seeds

        assert get_udp_seeds('udp://[2001::1]/announce', 'HASH') == 0
        assert get_udp_seeds('udp://[::1]/announce', 'HASH') == 0
        assert get_udp_seeds('udp://["2100::1"]:-1/announce', 'HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1/announce', 'HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1:-1/announce', 'HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1:PORT/announce', 'HASH') == 0
        assert get_udp_seeds('udp://127.0.0.1:65536/announce', 'HASH') == 0


class TestRtorrentMagnet:
    __tmp__ = True
    config = """
        tasks:
          test:
            mock:
              - title: 'test'
                url: 'magnet:?xt=urn:btih:HASH&dn=title&tr=http://torrent.ubuntu.com:6969/announce'
            rtorrent_magnet: __tmp__
            accept_all: yes
    """

    def test_rtorrent_magnet(self, execute_task, tmp_path):
        execute_task('test')
        fullpath = tmp_path.joinpath('meta-test.torrent')
        assert fullpath.is_file()
        assert (
            fullpath.read_text()
            == 'd10:magnet-uri76:magnet:?xt=urn:btih:HASH&dn=title&tr=http://torrent.ubuntu.com:6969/announcee'
        )
