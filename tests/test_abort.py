from __future__ import unicode_literals, division, absolute_import

from flexget import plugin
from flexget.event import event


class AbortPlugin(object):
    def on_task_output(self, task, config):
        task.abort('abort plugin')


@event('plugin.register')
def register():
    plugin.register(AbortPlugin, 'abort', debug=True, api_ver=2)


class TestAbort(object):

    config = """
        tasks:
          test:
            # causes on_task_abort to be called
            disable: builtins

            # causes abort
            abort: yes

            # another event hookup with this plugin
            headers:
              test: value
    """

    def test_abort(self, execute_task):
        execute_task('test', abort=True)
