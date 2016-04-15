from __future__ import unicode_literals, division, absolute_import
from future.moves.xmlrpc import client as xmlrpc_client

import os

import mock

from flexget.plugins.plugin_rtorrent import RTorrent

torrent_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'private.torrent')
torrent_url = 'file:///%s' % torrent_file
torrent_info_hash = '09977FE761B8D293AD8A929CCAF2E9322D525A6C'

with open(torrent_file, 'rb') as tor_file:
    torrent_raw = tor_file.read()


def compare_binary(obj1, obj2):
    # Used to compare xmlrpclib.binary objects within a mocked call
    if not type(obj1) == type(obj2):
        return False
    if obj1.data != obj2.data:
        return False
    return True


class Matcher(object):
    def __init__(self, compare, some_obj):
        self.compare = compare
        self.some_obj = some_obj

    def __eq__(self, other):
        return self.compare(self.some_obj, other)


@mock.patch('flexget.plugins.plugin_rtorrent.HTTPServerProxy')
class TestRTorrentClient(object):

    def test_version(self, mocked_proxy):
        mocked_client = mocked_proxy()
        mocked_client.system.client_version.return_value = '0.9.4'
        client = RTorrent('http://localhost/RPC2')

        assert client.version == [0, 9, 4]
        assert mocked_client.system.client_version.called

    def test_load(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.execute.throw.return_value = 0
        mocked_proxy.load.raw_start.return_value = 0

        client = RTorrent('http://localhost/RPC2')

        resp = client.load(
            torrent_raw,
            fields={'priority': 3, 'directory': '/data/downloads', 'custom1': 'testing'},
            start=True,
            mkdir=True,
        )

        assert resp == 0

        # Ensure mkdir was called
        mocked_proxy.execute.throw.assert_called_with('', 'mkdir', '-p', '/data/downloads')

        # Ensure load was called
        assert mocked_proxy.load.raw_start.called

        match_binary = Matcher(compare_binary, xmlrpc_client.Binary(torrent_raw))

        called_args = mocked_proxy.load.raw_start.call_args_list[0][0]
        assert len(called_args) == 5
        assert '' == called_args[0]
        assert match_binary in called_args

        fields = [p for p in called_args[2:]]
        assert len(fields) == 3
        assert 'd.directory.set=\\/data\\/downloads' in fields
        assert 'd.custom1.set=testing' in fields
        assert 'd.priority.set=3' in fields

    def test_torrent(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.system.multicall.return_value = [
            ['/data/downloads'], ['private.torrent'], [torrent_info_hash], ['test_custom1'], [123456]
        ]

        client = RTorrent('http://localhost/RPC2')

        torrent = client.torrent(torrent_info_hash, fields=['custom1', 'down_rate'])  # Required fields should be added

        assert isinstance(torrent, dict)
        assert torrent.get('base_path') == '/data/downloads'
        assert torrent.get('hash') == torrent_info_hash
        assert torrent.get('custom1') == 'test_custom1'
        assert torrent.get('name') == 'private.torrent'
        assert torrent.get('down_rate') == 123456

        assert mocked_proxy.system.multicall.called_with(([
            {'params': (torrent_info_hash,), 'methodName': 'd.base_path'},
            {'params': (torrent_info_hash,), 'methodName': 'd.name'},
            {'params': (torrent_info_hash,), 'methodName': 'd.hash'},
            {'params': (torrent_info_hash,), 'methodName': 'd.custom1'},
            {'params': (torrent_info_hash,), 'methodName': 'd.down.rate'},
        ]))

    def test_torrents(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        hash1 = '09977FE761AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
        hash2 = '09977FE761BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'

        mocked_proxy.d.multicall.return_value = (
            ['/data/downloads', 'private.torrent', hash1, 'test_custom1'],
            ['/data/downloads', 'private.torrent', hash2, 'test_custom2'],
        )

        client = RTorrent('http://localhost/RPC2')
        torrents = client.torrents(fields=['custom1'])  # Required fields should be added

        assert isinstance(torrents, list)

        for torrent in torrents:
            assert torrent.get('base_path') == '/data/downloads'
            assert torrent.get('name') == 'private.torrent'

            if torrent.get('hash') == hash1:
                assert torrent.get('custom1') == 'test_custom1'
            elif torrent.get('hash') == hash2:
                assert torrent.get('custom1') == 'test_custom2'
            else:
                assert False, 'Invalid hash returned'

        assert mocked_proxy.system.multicall.called_with((
            ['main', 'd.directory_base=', 'd.name=', 'd.hash=', u'd.custom1='],
        ))

    def test_update(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.system.multicall.return_value = [[0]]

        client = RTorrent('http://localhost/RPC2')

        update_fields = {
            'custom1': 'test_custom1',
            'directory_base': '/data/downloads',
            'priority': 3,
        }

        resp = client.update(torrent_info_hash, fields=update_fields)
        assert resp == 0

        assert mocked_proxy.system.multicall.called_with(([
            {'params': (torrent_info_hash, '/data/downloads'), 'methodName': 'd.directory_base'},
            {'params': (torrent_info_hash, 'test_custom1'), 'methodName': 'd.custom1'},
            {'params': (torrent_info_hash, '/data/downloads'), 'methodName': 'd.custom1'}
        ]))

    def test_delete(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.d.erase.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.delete(torrent_info_hash)

        assert resp == 0
        assert mocked_proxy.d.erase.called_with((torrent_info_hash,))

    def test_move(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.system.multicall.return_value = [
            ['private.torrent'], [torrent_info_hash], ['/data/downloads'],
        ]

        mocked_proxy.move.return_value = 0
        mocked_proxy.d.directory.set.return_value = 0
        mocked_proxy.execute.throw.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        client.move(torrent_info_hash, '/new/folder')

        mocked_proxy.execute.throw.assert_has_calls([
            mock.call('', 'mkdir', '-p', '/new/folder'),
            mock.call('', 'mv', '-u', '/data/downloads', '/new/folder'),
        ])

    def test_start(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.d.start.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.start(torrent_info_hash)

        assert resp == 0
        assert mocked_proxy.d.start.called_with((torrent_info_hash,))

    def test_stop(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.d.close.return_value = 0
        mocked_proxy.d.stop.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.stop(torrent_info_hash)

        assert resp == 0
        assert mocked_proxy.d.stop.called_with((torrent_info_hash,))
        assert mocked_proxy.d.close.called_with((torrent_info_hash,))


@mock.patch('flexget.plugins.plugin_rtorrent.RTorrent')
class TestRTorrentOutputPlugin(object):

    config = """
        tasks:
          test_add_torrent:
            accept_all: yes
            mock:
              - {title: 'test', url: '""" + torrent_url + """'}
            rtorrent:
              action: add
              start: yes
              mkdir: yes
              uri: http://localhost/SCGI
              priority: high
              path: /data/downloads
              custom1: test_custom1
          test_add_torrent_set:
            accept_all: yes
            set:
              path: /data/downloads
              custom1: test_custom1
              priority: low
              custom2: test_custom2
            mock:
              - {title: 'test', url: '""" + torrent_url + """'}
            rtorrent:
              action: add
              start: no
              mkdir: no
              uri: http://localhost/SCGI
          test_update:
            accept_all: yes
            set:
              path: /data/downloads
              priority: low
            mock:
              - {title: 'test', url: '""" + torrent_url + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: update
              uri: http://localhost/SCGI
              custom1: test_custom1
          test_update_path:
            accept_all: yes
            mock:
              - {title: 'test', url: '""" + torrent_url + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: update
              custom1: test_custom1
              uri: http://localhost/SCGI
              path: /new/path
          test_delete:
            accept_all: yes
            mock:
              - {title: 'test', url: '""" + torrent_url + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: delete
              uri: http://localhost/SCGI
              custom1: test_custom1
    """

    def test_add(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.load.return_value = 0
        mocked_client.version = [0, 9, 4]
        mocked_client.torrent.side_effect = [False, {'hash': torrent_info_hash}]

        execute_task('test_add_torrent')

        mocked_client.load.assert_called_with(
            torrent_raw,
            fields={'priority': 3, 'directory': '/data/downloads', 'custom1': 'test_custom1'},
            start=True,
            mkdir=True,
        )

    def test_add_set(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.load.return_value = 0
        mocked_client.version = [0, 9, 4]
        mocked_client.torrent.side_effect = [False, {'hash': torrent_info_hash}]

        execute_task('test_add_torrent_set')

        mocked_client.load.assert_called_with(
            torrent_raw,
            fields={
                'priority': 1,
                'directory': '/data/downloads',
                'custom1': 'test_custom1',
                'custom2': 'test_custom2'
            },
            start=False,
            mkdir=False,
        )

    def test_update(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.version = [0, 9, 4]
        mocked_client.update.return_value = 0
        # ntpath complains on windows if base_path is a MagicMock
        mocked_client.torrent.side_effect = [False, {'base_path': ''}]

        execute_task('test_update')

        mocked_client.update.assert_called_with(
            torrent_info_hash,
            {'priority': 1, 'custom1': 'test_custom1'}
        )

    def test_update_path(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.version = [0, 9, 4]
        mocked_client.update.return_value = 0
        mocked_client.move.return_value = 0
        mocked_client.torrent.return_value = {'base_path': '/some/path'}

        execute_task('test_update_path')

        mocked_client.update.assert_called_with(
            torrent_info_hash,
            {'custom1': 'test_custom1'}
        )

        mocked_client.move.assert_called_with(
            torrent_info_hash,
            '/new/path',
        )

    def test_delete(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.load.return_value = 0
        mocked_client.version = [0, 9, 4]
        mocked_client.delete.return_value = 0

        execute_task('test_delete')

        mocked_client.delete.assert_called_with(torrent_info_hash)


@mock.patch('flexget.plugins.plugin_rtorrent.RTorrent')
class TestRTorrentInputPlugin(object):

    config = """
        tasks:
          test_input:
            accept_all: yes
            from_rtorrent:
              uri: http://localhost/RPC2
              view: complete
              fields:
                - custom1
                - custom3
                - down_rate

    """

    def test_input(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.version = [0, 9, 4]

        mocked_torrent = {
            'name': 'private.torrent',
            'hash': torrent_info_hash,
            'base_path': '/data/downloads/private',
            'custom1': 'test_custom1',
            'custom3': 'test_custom3',
            'down_rate': 123456,
        }

        mocked_client.torrents.return_value = [mocked_torrent, mocked_torrent]

        task = execute_task('test_input')

        mocked_client.torrents.assert_called_with(
            'complete',
            fields=['custom1', 'custom3', 'down_rate'],
        )

        assert len(task.all_entries) == 2

        for entry in task.entries:
            assert entry['url'] == 'http://localhost/RPC2/%s' % torrent_info_hash
            assert entry['name'] == 'private.torrent'
            assert entry['torrent_info_hash'] == torrent_info_hash
            assert entry['path'] == '/data/downloads/private'
            assert entry['custom1'] == 'test_custom1'
            assert entry['custom3'] == 'test_custom3'
