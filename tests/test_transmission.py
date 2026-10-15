import importlib.metadata
from unittest import mock

import pytest


@pytest.mark.require_optional_deps
@mock.patch('flexget.plugins.clients.transmission.transmission_rpc')
class TestTransmissionTorrentPlugin:
    config = """
        tasks:
            test_input:
                mock:
                    - {title: 'title1', url: 'url1', transmission_id: '321', file: 'file1'}
                accept_all: yes
                transmission:
                    host: localhost
                    port: 9091
                    username: myusername
                    password: mypassword
                    labels:
                      - "3"
                      - "1"
                      - z
                      - aaa
                      - "{{title}}"
    """

    def test_output_labels_order(self, mocked_transmission, execute_task):
        mocked_client = mocked_transmission.Client.return_value
        mocked_torrent = mock.Mock()
        mocked_torrent.id = '321'

        mocked_client.get_torrents.return_value = [mocked_torrent]

        task = execute_task('test_input')

        assert len(task.all_entries) == 1
        mocked_client.change_torrent.assert_called_with(
            '321', labels=['3', '1', 'z', 'aaa', 'title1']
        )

    @mock.patch(
        'flexget.plugins.clients.transmission.importlib.metadata.version',
        side_effect=importlib.metadata.PackageNotFoundError('transmission-rpc'),
    )
    def test_metadata_gone_after_import(self, mocked_version, mocked_transmission, execute_task):
        """The metadata of the imported module can disappear while the daemon runs (#5262)."""
        mocked_client = mocked_transmission.Client.return_value
        mocked_torrent = mock.Mock()
        mocked_torrent.id = '321'
        mocked_client.get_torrents.return_value = [mocked_torrent]

        task = execute_task('test_input')

        assert not task.aborted
        mocked_client.change_torrent.assert_called()

    @mock.patch('flexget.plugins.clients.transmission._installed_version', '6.0.0')
    def test_version_mismatch(self, mocked_transmission, execute_task):
        task = execute_task('test_input', abort=True)

        assert task.aborted
        assert 'module version mismatch' in task.abort_reason
