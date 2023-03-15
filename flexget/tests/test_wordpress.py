from unittest import mock

import pytest
from requests import RequestException
from requests.cookies import RequestsCookieJar
from requests.utils import cookiejar_from_dict

from flexget.task import TaskAbort


def _mock_session_response(mock_, monkeypatch):
    def mocked_send(*args, **kwargs):
        return mock_

    monkeypatch.setattr('requests.Session.send', mocked_send)


class TestWordPress:
    config = """
        tasks:
          test:
            wordpress_auth:
              url: http://example.org/wp-login.php
              username: johndoe
              password: qwerty
    """

    def test_task_aborts_for_status_not_ok(self, execute_task, monkeypatch):
        with pytest.raises(TaskAbort):
            _mock_session_response(mock.Mock(ok=False), monkeypatch)
            execute_task('test')

    def test_task_aborts_for_requests_exception(self, execute_task, monkeypatch):
        with pytest.raises(TaskAbort):
            monkeypatch.setattr('requests.Session.send', mock.Mock(side_effect=RequestException))
            execute_task('test')

    def test_task_aborts_when_response_has_no_valid_cookies(self, execute_task, monkeypatch):
        with pytest.raises(TaskAbort):
            invalid_cookies = {
                '__cfduid': '16a85284e4ee53f4933760b08b2bc82c',
                'wordpress_test_cookie': 'test+cookie',
            }
            _mock_session_response(
                mock.Mock(cookies=cookiejar_from_dict(invalid_cookies), history=[]), monkeypatch
            )
            execute_task('test')

    def test_cookies_collected_across_redirects(self, execute_task, monkeypatch):
        valid_cookies = {
            'wordpress_logged_in_a32b6': '16a85284e4ee53f4933760b08b2bc82c',
            'wordpress_sec': 'test_value',
        }
        mock_history = [mock.Mock(cookies=cookiejar_from_dict(valid_cookies))]
        _mock_session_response(
            mock.Mock(cookies=RequestsCookieJar(), history=mock_history), monkeypatch
        )
        task = execute_task('test')
        assert len(task.requests.cookies) > 0, 'No cookies found within response'
