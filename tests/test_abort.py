from __future__ import unicode_literals, division, absolute_import

from flexget import plugin
from flexget.event import event
from tests import FlexGetBase


class AbortPlugin(object):
    def on_task_output(self, task, config):
        task.abort('abort plugin')


@event('plugin.register')
def register():
    plugin.register(AbortPlugin, 'abort', debug=True, api_ver=2)


class TestAbort(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            # causes on_task_abort to be called
            disable_builtins: yes

            # causes abort
            abort: yes

            # another event hookup with this plugin
            headers:
              test: value
    """

    def test_abort(self):
        self.execute_task('test', abort_ok=True)
        assert self.task.aborted, 'Task not aborted'
