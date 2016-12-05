from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import mock

@mock.patch('requests.Session.request')
class TestNotifyAbort(object):
    config = """
        tasks:
          test_abort:
            # causes on_task_abort to be called
            disable: builtins

            # causes abort
            abort: yes

            notify_abort:
              to:
                - pushover:
                    user_key: user_key
          no_crash:
            disable: builtins
            notify_abort:
              to:
                - pushover:
                    user_key: user_key
    """

    def test_abort(self, mocked_request, execute_task):
        execute_task('test_abort', abort=True)
        data = {'message': 'Reason: abort plugin', 'title': 'Task test_abort has aborted!'}

        assert mocked_request.called

        for k, v in data.items():
            assert mocked_request.call_args[1]['data'][k] == v

    def test_no_crash(self, mocked_request, execute_task):
        execute_task('no_crash')
        assert not mocked_request.called
