from unittest import mock

import pytest
from requests import RequestException

from flexget.plugins.output.botarr import Botarr


class TestBotarr:
    config = """
        templates:
          global:
            disable: [retry_failed, urlrewriting]
        tasks:
          test_botarr_success:
            mock:
              - {title: 'TestFile.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001
              priority: high

          test_botarr_empty:
            mock:
              - {title: 'Empty.mkv', url: 'irc://Rizon'}
            botarr:
              url: http://localhost:3001

          test_botarr_no_url:
            mock:
              - {title: 'NoUrl.mkv'}
            accept_all: yes
            set:
              url: ''
            botarr:
              url: http://localhost:3001

          test_botarr_invalid_url:
            mock:
              - {title: 'Invalid.mkv', url: 'http://example.com/file'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_learn:
            mock:
              - {title: 'Learn.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_test_mode:
            mock:
              - {title: 'TestMode.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_duplicate:
            mock:
              - {title: 'Dup.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_http_error:
            mock:
              - {title: 'Error.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_connection_error:
            mock:
              - {title: 'ConnError.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_no_transfer_id:
            mock:
              - {title: 'NoId.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001

          test_botarr_poll_completed:
            mock:
              - {title: 'PollComp.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001
              poll_for_result: yes
              poll_interval: 5
              poll_timeout: 60

          test_botarr_poll_failed:
            mock:
              - {title: 'PollFail.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001
              poll_for_result: yes
              poll_interval: 5
              poll_timeout: 60

          test_botarr_poll_timeout:
            mock:
              - {title: 'PollTimeout.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001
              poll_for_result: yes
              poll_interval: 5
              poll_timeout: 60

          test_botarr_poll_404:
            mock:
              - {title: 'Poll404.mkv', url: 'irc://Rizon/#channel/Bot/#1'}
            accept_all: yes
            botarr:
              url: http://localhost:3001
              poll_for_result: yes
              poll_interval: 5
              poll_timeout: 60
    """

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_submit(self, mock_post, execute_task):
        mock_response = mock.Mock()
        mock_response.json.return_value = {'transfer_id': 'test-uuid-1234'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        task = execute_task('test_botarr_success')
        assert len(task.accepted) == 1
        entry = task.accepted[0]

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == 'http://localhost:3001/api/download'
        assert kwargs['json']['url'] == 'irc://Rizon/#channel/Bot/#1'
        assert kwargs['json']['priority'] == 'high'
        assert kwargs['json']['filename'] == 'TestFile.mkv'
        assert entry.get('botarr_transfer_id') == 'test-uuid-1234'
        assert not entry.failed

    def test_botarr_no_url(self, execute_task):
        task = execute_task('test_botarr_no_url')
        assert len(task.all_entries) == 1
        assert task.all_entries[0].failed

    def test_botarr_empty(self, execute_task):
        task = execute_task('test_botarr_empty')
        assert len(task.accepted) == 0

    def test_botarr_invalid_url(self, execute_task):
        task = execute_task('test_botarr_invalid_url')
        assert len(task.all_entries) == 1
        assert task.all_entries[0].failed

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_learn(self, mock_post, execute_task):
        task = execute_task('test_botarr_learn', options=dict(learn=True))
        mock_post.assert_not_called()

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_learn_manual(self, mock_post, execute_task):
        task = execute_task('test_botarr_success')
        mock_post.reset_mock()
        task.options.learn = True
        from flexget.plugins.output.botarr import Botarr
        Botarr().on_task_output(task, {'url': 'http://localhost:3001', 'priority': 'normal', 'poll_for_result': False})
        mock_post.assert_not_called()

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_test_mode(self, mock_post, execute_task):
        task = execute_task('test_botarr_test_mode', options={'test': True})
        assert len(task.accepted) == 1
        assert not task.accepted[0].failed
        mock_post.assert_not_called()

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_duplicate(self, mock_post, execute_task):
        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = RequestException(response=mock.Mock(
            json=lambda: {'error': 'Duplicate release detected'},
            text='Duplicate release detected'
        ))
        mock_post.return_value = mock_response

        task = execute_task('test_botarr_duplicate')
        assert len(task.accepted) == 1
        # Duplicate shouldn't fail the entry, just logs info
        assert not task.accepted[0].failed

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_http_error(self, mock_post, execute_task):
        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = RequestException(response=mock.Mock(
            json=mock.Mock(side_effect=ValueError("Invalid JSON")),
            text='Some other error'
        ))
        mock_post.return_value = mock_response

        task = execute_task('test_botarr_http_error')
        assert len(task.all_entries) == 1
        assert task.all_entries[0].failed

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_connection_error(self, mock_post, execute_task):
        mock_post.side_effect = RequestException('Connection timeout')
        task = execute_task('test_botarr_connection_error')
        assert len(task.all_entries) == 1
        assert task.all_entries[0].failed

    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_no_transfer_id(self, mock_post, execute_task):
        mock_response = mock.Mock()
        mock_response.json.return_value = {}  # No transfer_id
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        task = execute_task('test_botarr_no_transfer_id')
        assert len(task.accepted) == 1
        assert not task.accepted[0].failed
        assert 'botarr_transfer_id' not in task.accepted[0]

    @mock.patch('flexget.utils.requests.Session.get')
    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_poll_completed(self, mock_post, mock_get, execute_task):
        mock_post_resp = mock.Mock()
        mock_post_resp.json.return_value = {'transfer_id': 'poll-1'}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        mock_get_resp = mock.Mock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            'transfer': {'status': 'completed', 'filename': 'PollComp.mkv', 'size': 12345}
        }
        mock_get.return_value = mock_get_resp

        task = execute_task('test_botarr_poll_completed')
        assert len(task.accepted) == 1
        entry = task.accepted[0]
        assert entry.get('botarr_status') == 'completed'
        assert entry.get('botarr_filename') == 'PollComp.mkv'
        assert entry.get('botarr_size') == 12345
        assert not entry.failed

    @mock.patch('flexget.utils.requests.Session.get')
    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_poll_failed(self, mock_post, mock_get, execute_task):
        mock_post_resp = mock.Mock()
        mock_post_resp.json.return_value = {'transfer_id': 'poll-2'}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        mock_get_resp = mock.Mock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            'transfer': {'status': 'failed', 'error': 'CRC mismatch'}
        }
        mock_get.return_value = mock_get_resp

        task = execute_task('test_botarr_poll_failed')
        assert len(task.all_entries) == 1
        entry = task.all_entries[0]
        assert entry.get('botarr_status') == 'failed'
        assert entry.failed

    @mock.patch('time.sleep')
    @mock.patch('flexget.utils.requests.Session.get')
    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_poll_timeout(self, mock_post, mock_get, mock_sleep, execute_task):
        mock_post_resp = mock.Mock()
        mock_post_resp.json.return_value = {'transfer_id': 'poll-3'}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        mock_get_resp = mock.Mock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {'transfer': {'status': 'downloading', 'progress': 50.0}}
        mock_get.return_value = mock_get_resp

        # Mock time.time to simulate timeout immediately
        with mock.patch('time.time', side_effect=[0, 0, 70, 80]):
            task = execute_task('test_botarr_poll_timeout')

        assert len(task.accepted) == 1
        assert not task.accepted[0].failed

    @mock.patch('flexget.utils.requests.Session.get')
    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_poll_404(self, mock_post, mock_get, execute_task):
        mock_post_resp = mock.Mock()
        mock_post_resp.json.return_value = {'transfer_id': 'poll-4'}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        mock_get_resp = mock.Mock()
        mock_get_resp.status_code = 404
        mock_get.return_value = mock_get_resp

        task = execute_task('test_botarr_poll_404')
        assert len(task.all_entries) == 1
        assert task.all_entries[0].failed

    @mock.patch('time.sleep')
    @mock.patch('flexget.utils.requests.Session.get')
    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_poll_500(self, mock_post, mock_get, mock_sleep, execute_task):
        mock_post_resp = mock.Mock()
        mock_post_resp.json.return_value = {'transfer_id': 'poll-500'}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        mock_get_resp = mock.Mock()
        mock_get_resp.status_code = 500
        mock_get.return_value = mock_get_resp

        with mock.patch('time.time', side_effect=[0, 0, 70, 80]):
            execute_task('test_botarr_poll_404')

    @mock.patch('time.sleep')
    @mock.patch('flexget.utils.requests.Session.get')
    @mock.patch('flexget.utils.requests.Session.post')
    def test_botarr_poll_exception(self, mock_post, mock_get, mock_sleep, execute_task):
        mock_post_resp = mock.Mock()
        mock_post_resp.json.return_value = {'transfer_id': 'poll-exc'}
        mock_post_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_post_resp

        mock_get.side_effect = RequestException("Poll error")

        with mock.patch('time.time', side_effect=[0, 0, 70, 80]):
            execute_task('test_botarr_poll_404')
