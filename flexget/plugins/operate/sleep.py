import time

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='sleep')


class PluginSleep:
    """
    Causes a pause in execution to occur at the beginning of the specified phase of a task.
    The point at which the pause occurs can be adjusted using the `plugin_priority` plugin.
    """

    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'seconds': {'type': 'integer'},
                    'phase': {
                        'type': 'string',
                        'enum': [
                            'start',
                            'input',
                            'metainfo',
                            'filter',
                            'download',
                            'modify',
                            'output',
                            'learn',
                            'abort',
                            'exit',
                        ],
                        'default': 'start',
                    },
                },
                'required': ['seconds'],
                'additionalProperties': False,
            },
            {'type': 'integer'},
        ]
    }

    def do_sleep(self, config, phase):
        if isinstance(config, int):
            config = {'phase': 'start', 'seconds': config}
        if config and config['phase'] == phase:
            logger.verbose('Sleeping for {} seconds.', config['seconds'])
            time.sleep(int(config['seconds']))

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_start(self, task, config):
        self.do_sleep(config, 'start')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_input(self, task, config):
        self.do_sleep(config, 'input')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_metainfo(self, task, config):
        self.do_sleep(config, 'metainfo')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        self.do_sleep(config, 'filter')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_download(self, task, config):
        self.do_sleep(config, 'download')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_modify(self, task, config):
        self.do_sleep(config, 'modify')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_output(self, task, config):
        self.do_sleep(config, 'output')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_learn(self, task, config):
        self.do_sleep(config, 'learn')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_abort(self, task, config):
        self.do_sleep(config, 'abort')

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_exit(self, task, config):
        self.do_sleep(config, 'exit')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSleep, 'sleep', api_ver=2)
