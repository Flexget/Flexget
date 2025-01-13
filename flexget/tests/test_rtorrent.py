import os
import re
from unittest import mock
from xmlrpc import client as xmlrpc_client

from flexget.plugins.clients.rtorrent import RTorrent

torrent_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'private.torrent')
torrent_url = f'file:///{torrent_file}'
torrent_info_hash = '09977FE761B8D293AD8A929CCAF2E9322D525A6C'

with open(torrent_file, 'rb') as tor_file:
    torrent_raw = tor_file.read()


@mock.patch('flexget.plugins.clients.rtorrent.xmlrpc_client.ServerProxy')
class TestRTorrentClient:
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

        called_args = mocked_proxy.load.raw_start.call_args_list[0][0]
        assert len(called_args) == 5
        assert called_args[0] == ''
        assert xmlrpc_client.Binary(torrent_raw) in called_args

        fields = list(called_args[2:])
        assert len(fields) == 3
        # TODO: check the note in clients/rtorrent.py about this escaping.
        # The client should be fixed to work consistenly on all python versions
        # Calling re.escape here is a workaround so test works on python 3.7 and older versions
        assert ('d.directory.set=' + re.escape('/data/downloads')) in fields
        assert 'd.custom1.set=testing' in fields
        assert 'd.priority.set=3' in fields

    def test_torrent(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.system.multicall.return_value = [
            ['/data/downloads'],
            ['private.torrent'],
            [torrent_info_hash],
            ['test_custom1'],
            [123456],
        ]

        client = RTorrent('http://localhost/RPC2')

        torrent = client.torrent(
            torrent_info_hash, fields=['custom1', 'down_rate']
        )  # Required fields should be added

        assert isinstance(torrent, dict)
        assert torrent.get('base_path') == '/data/downloads'
        assert torrent.get('hash') == torrent_info_hash
        assert torrent.get('custom1') == 'test_custom1'
        assert torrent.get('name') == 'private.torrent'
        assert torrent.get('down_rate') == 123456

        mocked_proxy.system.multicall.assert_called_with(
            [
                {'params': (torrent_info_hash,), 'methodName': 'd.base_path'},
                {'params': (torrent_info_hash,), 'methodName': 'd.name'},
                {'params': (torrent_info_hash,), 'methodName': 'd.hash'},
                {'params': (torrent_info_hash,), 'methodName': 'd.custom1'},
                {'params': (torrent_info_hash,), 'methodName': 'd.down.rate'},
            ]
        )

    def test_torrents(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        hash1 = '09977FE761AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
        hash2 = '09977FE761BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'

        mocked_proxy.d.multicall2.return_value = (
            ['/data/downloads', 'private.torrent', hash1, 'test_custom1'],
            ['/data/downloads', 'private.torrent', hash2, 'test_custom2'],
        )

        client = RTorrent('http://localhost/RPC2')
        torrents = client.torrents(fields=['custom1'])  # Required fields should be added

        assert isinstance(torrents, list)
        assert len(torrents) == 2

        for torrent in torrents:
            assert torrent.get('base_path') == '/data/downloads'
            assert torrent.get('name') == 'private.torrent'

            if torrent.get('hash') == hash1:
                assert torrent.get('custom1') == 'test_custom1'
            elif torrent.get('hash') == hash2:
                assert torrent.get('custom1') == 'test_custom2'
            else:
                raise AssertionError('Invalid hash returned')

        mocked_proxy.d.multicall2.assert_called_with(
            '', ['main', 'd.base_path=', 'd.name=', 'd.hash=', 'd.custom1=']
        )

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

        mocked_proxy.system.multicall.assert_called_with(
            [
                {'params': (torrent_info_hash, 'test_custom1'), 'methodName': 'd.custom1.set'},
                {
                    'params': (torrent_info_hash, '/data/downloads'),
                    'methodName': 'd.directory_base.set',
                },
                {'params': (torrent_info_hash, 3), 'methodName': 'd.priority.set'},
            ]
        )

    def test_delete(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.d.erase.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.delete(torrent_info_hash)

        assert resp == 0
        mocked_proxy.d.erase.assert_called_with(torrent_info_hash)

    def test_purge_torrent(self, mocked_proxy):
        mocked_proxy = mocked_proxy()

        mocked_proxy.system.multicall.return_value = [
            ['ubuntu-9.04-desktop-amd64.iso'],
            [torrent_info_hash],
            ['/data/downloads/ubuntu-9.04-desktop-amd64.iso'],
        ]

        mocked_proxy.d.stop.return_value = 0
        mocked_proxy.d.close.return_value = 0
        mocked_proxy.d.erase.return_value = 0
        mocked_proxy.execute.throw.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.purge_torrent(torrent_info_hash)

        assert resp == 0

        mocked_proxy.execute.throw.assert_has_calls(
            [
                mock.call('', 'rm', '-drf', '/data/downloads/ubuntu-9.04-desktop-amd64.iso'),
            ]
        )

    def test_move(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.system.multicall.return_value = [
            ['private.torrent'],
            [torrent_info_hash],
            ['/data/downloads'],
        ]

        mocked_proxy.move.return_value = 0
        mocked_proxy.d.directory.set.return_value = 0
        mocked_proxy.execute.throw.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        client.move(torrent_info_hash, '/new/folder')

        mocked_proxy.execute.throw.assert_has_calls(
            [
                mock.call('', 'mkdir', '-p', '/new/folder'),
                mock.call('', 'mv', '-u', '/data/downloads', '/new/folder'),
            ]
        )

    def test_start(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.d.start.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.start(torrent_info_hash)

        assert resp == 0
        mocked_proxy.d.start.assert_called_with(torrent_info_hash)

    def test_stop(self, mocked_proxy):
        mocked_proxy = mocked_proxy()
        mocked_proxy.d.close.return_value = 0
        mocked_proxy.d.stop.return_value = 0

        client = RTorrent('http://localhost/RPC2')
        resp = client.stop(torrent_info_hash)

        assert resp == 0
        mocked_proxy.d.stop.assert_called_with(torrent_info_hash)
        mocked_proxy.d.close.assert_called_with(torrent_info_hash)


@mock.patch('flexget.plugins.clients.rtorrent.RTorrent')
class TestRTorrentOutputPlugin:
    variable_value = 'variable field jinja replacesment test value'
    entry_field_value = 'entry field jinja replacement test value'
    config = (
        """
        variables:
            rtorrent_variable_test: '"""
        + variable_value
        + """'
        tasks:
          test_add_torrent:
            accept_all: yes
            mock:
              - {title: 'test', url: '"""
        + torrent_url
        + """'}
            set:
              rtorrent_test_add_val: '"""
        + entry_field_value
        + """'
            rtorrent:
              action: add
              start: yes
              mkdir: yes
              uri: http://localhost/SCGI
              priority: high
              path: /data/downloads
              custom1: test_custom1
              custom_fields:
                named_custom_field_1: named custom field value 1
                named_custom_field_2: Test variable substitution - '{? rtorrent_variable_test ?}'
                named_custom_field_3: Test entry field substitution - '{{rtorrent_test_add_val}}'
          test_add_torrent_set:
            accept_all: yes
            set:
              path: /data/downloads
              custom1: test_custom1
              priority: low
              custom2: test_custom2
              custom_fields:
                named_custom_field_1: named custom field value 1
            mock:
              - {title: 'test', url: '"""
        + torrent_url
        + """'}
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
              - {title: 'test', url: '"""
        + torrent_url
        + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: update
              uri: http://localhost/SCGI
              custom1: test_custom1
              custom_fields:
                named_custom_field_1: named custom field value 1 update
                named_custom_field_update_1: some value
          test_update_path:
            accept_all: yes
            mock:
              - {title: 'test', url: '"""
        + torrent_url
        + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: update
              custom1: test_custom1
              uri: http://localhost/SCGI
              path: /new/path
              custom_fields:
                named_custom_field_1: named custom field value 1 update again
                named_custom_field_update_2: some value again
          test_delete:
            accept_all: yes
            mock:
              - {title: 'test', url: '"""
        + torrent_url
        + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: delete
              uri: http://localhost/SCGI
              custom1: test_custom1
          test_purge:
            accept_all: yes
            mock:
              - {title: 'test', url: '"""
        + torrent_url
        + """', 'torrent_info_hash': '09977FE761B8D293AD8A929CCAF2E9322D525A6C'}
            rtorrent:
              action: purge
              uri: http://localhost/SCGI
    """
    )

    def test_add(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.load.return_value = 0
        mocked_client.version = [0, 9, 4]
        mocked_client.torrent.side_effect = [False, {'hash': torrent_info_hash}]

        execute_task('test_add_torrent')

        mocked_client.load.assert_called_with(
            torrent_raw,
            fields={'priority': 3, 'directory': '/data/downloads', 'custom1': 'test_custom1'},
            custom_fields={
                'named_custom_field_1': 'named custom field value 1',
                'named_custom_field_2': "Test variable substitution - '"
                + self.variable_value
                + "'",
                'named_custom_field_3': "Test entry field substitution - '"
                + self.entry_field_value
                + "'",
            },
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
                'custom2': 'test_custom2',
            },
            custom_fields={
                'named_custom_field_1': 'named custom field value 1',
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
            info_hash=torrent_info_hash,
            fields={'priority': 1, 'custom1': 'test_custom1'},
            custom_fields={
                'named_custom_field_1': 'named custom field value 1 update',
                'named_custom_field_update_1': 'some value',
            },
        )

    def test_update_path(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.version = [0, 9, 4]
        mocked_client.update.return_value = 0
        mocked_client.move.return_value = 0
        mocked_client.torrent.return_value = {'base_path': '/some/path'}

        execute_task('test_update_path')

        mocked_client.update.assert_called_with(
            info_hash=torrent_info_hash,
            fields={'custom1': 'test_custom1'},
            custom_fields={
                'named_custom_field_1': 'named custom field value 1 update again',
                'named_custom_field_update_2': 'some value again',
            },
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

    def test_purge(self, mocked_client, execute_task):
        mocked_client = mocked_client()
        mocked_client.load.return_value = 0
        mocked_client.version = [0, 9, 4]
        mocked_client.purge_torrent.return_value = 0

        execute_task('test_purge')

        mocked_client.purge_torrent.assert_called_with(torrent_info_hash)


@mock.patch('flexget.plugins.clients.rtorrent.RTorrent')
class TestRTorrentInputPlugin:
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
              custom_fields:
                - foo
                - bar
                - foobar
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
            custom_fields=['foo', 'bar', 'foobar'],
        )

        assert len(task.all_entries) == 2

        for entry in task.entries:
            assert entry['url'] == f'http://localhost/RPC2/{torrent_info_hash}'
            assert entry['name'] == 'private.torrent'
            assert entry['torrent_info_hash'] == torrent_info_hash
            assert entry['path'] == '/data/downloads/private'
            assert entry['custom1'] == 'test_custom1'
            assert entry['custom3'] == 'test_custom3'
