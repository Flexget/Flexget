from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import mock

from flexget import plugin
from flexget.event import event


class AbortPlugin(object):
    def on_task_output(self, task, config):
        task.abort('abort plugin')


@event('plugin.register')
def register():
    plugin.register(AbortPlugin, 'abort', debug=True, api_ver=2)


@mock.patch('requests.Session.request')
class TestNotifyCrash(object):
    config = """
        tasks:
          test_crash:
            # causes on_task_abort to be called
            disable: builtins

            # causes abort
            abort: yes

            notify_crash:
              to:
                - pushbullet:
                    apikey: "apikey"
          no_crash:
            disable: builtins
            notify_crash:
              to:
                - pushbullet:
                    apikey: "apikey"
    """

    def test_abort(self, mocked_request, execute_task):
        execute_task('test_crash', abort=True)
        data = {'body': 'Task returned 0 accepted entries', 'title': 'test_crash'}

        assert mocked_request.called

        for k, v in data.items():
            assert mocked_request.call_args[1]['json'][k] == v

    def test_no_crash(self, mocked_request, execute_task):
        execute_task('no_crash')
        assert not mocked_request.called
