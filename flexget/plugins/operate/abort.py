from flexget import plugin
from flexget.event import event


class AbortPlugin:
    """
    abort plugin for debug purposes.

    Usage::

        abort: yes
    """

    def on_task_output(self, task, config):
        task.abort('abort plugin')


@event('plugin.register')
def register():
    plugin.register(AbortPlugin, 'abort', debug=True, api_ver=2)
