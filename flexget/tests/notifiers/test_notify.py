from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import mock


@mock.patch('requests.Session.request')
class TestNotify(object):
    config = """
        tasks:
          test_basic_notify:
            mock:
             - {title: "foo", url: 'http://bla.com'}
            accept_all: yes
            notify:
              to:
                - pushbullet:
                    apikey: "apikey"
                - pushbullet:
                    apikey: "apikey"
                - pushbullet:
                    apikey: "apikey"
        """

    def test_basic_notify(self, mocked_request, execute_task):
        params = {'body': 'foo', 'title': 'test_basic_notify'}
        task = execute_task('test_basic_notify')

        assert len(task.accepted) == 1
        assert mocked_request.call_count == 3

        for k, v in params.items():
            assert mocked_request.call_args[1]['json'][k] == v
