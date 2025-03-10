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
