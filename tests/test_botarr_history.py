from unittest import mock

import pytest
from requests import RequestException


class TestBotarrHistory:
    config = """
        tasks:
          test_history:
            botarr_history:
              url: http://localhost:3001
              only_new: no
              
          test_history_status:
            botarr_history:
              url: http://localhost:3001
              status: Completed
              only_new: no

          test_history_only_new:
            botarr_history:
              url: http://localhost:3001
              only_new: yes

          test_history_error:
            botarr_history:
              url: http://localhost:3001
    """

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_history(self, mock_get, execute_task):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {
            'items': [
                {
                    'id': 'uuid-1',
                    'status': 'Completed',
                    'file_name': 'File1.mkv',
                    'network': 'Rizon',
                    'channel': '#channel1',
                    'bot': 'Bot1',
                    'slot': 100,
                    'size': 1024,
                },
                {
                    'id': 'uuid-2',
                    'status': 'Failed',
                    'file_name': 'File2.mkv',
                    'error': 'CRC mismatch',
                },
                {
                    'status': 'Completed',
                    'file_name': 'File3.mkv',
                },
            ],
            'total': 3,
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        task = execute_task('test_history')
        assert len(task.entries) == 3

        e1, e2, e3 = task.entries
        assert e1['title'] == 'File1.mkv'
        assert e1['url'] == 'irc://Rizon/#channel1/Bot1/100'
        assert e1['botarr_transfer_id'] == 'uuid-1'
        assert e1['botarr_status'] == 'Completed'
        assert e1['botarr_size'] == 1024

        assert e2['title'] == 'File2.mkv'
        assert e2['botarr_transfer_id'] == 'uuid-2'
        assert e2['botarr_status'] == 'Failed'
        assert e2['botarr_error'] == 'CRC mismatch'

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_history_status(self, mock_get, execute_task):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {
            'items': [
                {'id': 'uuid-1', 'status': 'Completed', 'file_name': 'File1.mkv'},
                {'id': 'uuid-2', 'status': 'Failed', 'file_name': 'File2.mkv'},
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        task = execute_task('test_history_status')
        assert len(task.entries) == 1
        assert task.entries[0]['title'] == 'File1.mkv'

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_history_only_new(self, mock_get, execute_task):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {
            'items': [
                {'id': 'uuid-1', 'status': 'Completed', 'file_name': 'File1.mkv'},
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        # First run should produce the entry
        task1 = execute_task('test_history_only_new')
        assert len(task1.entries) == 1

        # Second run with same data should produce 0 entries due to only_new
        task2 = execute_task('test_history_only_new')
        assert len(task2.entries) == 0

        # Now add a new item
        mock_resp.json.return_value = {
            'items': [
                {'id': 'uuid-1', 'status': 'Completed', 'file_name': 'File1.mkv'},
                {'id': 'uuid-2', 'status': 'Completed', 'file_name': 'File2.mkv'},
            ]
        }
        task3 = execute_task('test_history_only_new')
        assert len(task3.entries) == 1
        assert task3.entries[0]['title'] == 'File2.mkv'

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_history_error(self, mock_get, execute_task):
        mock_get.side_effect = RequestException('Connection error')

        with pytest.raises(Exception) as excinfo:
            execute_task('test_history_error')

        assert 'Failed to fetch Botarr history' in str(excinfo.value)
