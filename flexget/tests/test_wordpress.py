from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import mock
import pytest

from requests import RequestException
from requests.utils import cookiejar_from_dict
from requests.cookies import RequestsCookieJar

from flexget.task import TaskAbort


class TestWordPress(object):
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
            def mocked_send(*args, **kwargs):
                return mock.Mock(ok=False)

            monkeypatch.setattr('flexget.plugins.sites.wordpress.WPSession.send', mocked_send)
            execute_task('test')

    def test_task_aborts_for_requests_exception(self, execute_task, monkeypatch):
        with pytest.raises(TaskAbort):
            monkeypatch.setattr('flexget.plugins.sites.wordpress.WPSession.send',
                                mock.Mock(side_effect=RequestException))
            execute_task('test')

    def test_log_writes_warning_for_no_valid_cookies(self, execute_task, monkeypatch):
        invalid_cookies = {'__cfduid': '16a85284e4ee53f4933760b08b2bc82c', 'wordpress_test_cookie': 'test+cookie'}

        def mocked_send(*args, **kwargs):
            return mock.Mock(cookies=cookiejar_from_dict(invalid_cookies), history=[])

        monkeypatch.setattr('flexget.plugins.sites.wordpress.WPSession.send', mocked_send)
        mock_log_warning = mock.Mock()
        monkeypatch.setattr('flexget.plugins.sites.wordpress.log.warning', mock_log_warning)
        execute_task('test')
        mock_log_warning.assert_called()

    def test_cookies_collected_across_redirects(self, execute_task, monkeypatch):
        valid_cookies = {'wordpress_logged_in_a32b6': '16a85284e4ee53f4933760b08b2bc82c', 'wordpress_sec': 'test_value'}

        def mocked_send(*args, **kwargs):
            return mock.Mock(cookies=RequestsCookieJar(), history=[
                mock.Mock(cookies=cookiejar_from_dict(valid_cookies))
            ])

        monkeypatch.setattr('flexget.plugins.sites.wordpress.WPSession.send', mocked_send)
        task = execute_task('test')
        assert len(task.requests.cookies) > 0, 'No cookies found within response'
