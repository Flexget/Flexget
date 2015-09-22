from __future__ import unicode_literals, division, absolute_import
import logging
import time

from flexget import plugin
from flexget.event import event

log = logging.getLogger('sleep')


class PluginSleep(object):
    """Causes a pause to occur during the specified phase of a task"""
    
    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'seconds': {'type': 'integer'},
                    'phase': {
                        'type': 'string',
                        'enum': ['start', 'input', 'metainfo', 'filter', 'download',
                                 'modify', 'output', 'learn', 'abort', 'exit'],
                        'default': 'start'
                    }
                },
                'required': ['seconds'],
                'additionalProperties': False
            },
            {'type': 'integer'}
        ]
    }

    def do_sleep(self, config, phase):
        if isinstance(config, int):
            config = {'phase': 'start', 'seconds': config}
        if config and config['phase'] == phase:
            log.verbose('Sleeping for %d seconds.' % config['seconds'])
            time.sleep(int(config['seconds']))

    @plugin.priority(255)
    def on_task_start(self, task, config):
        self.do_sleep(config, 'start')

    @plugin.priority(255)
    def on_task_input(self, task, config):
        self.do_sleep(config, 'input')

    @plugin.priority(255)
    def on_task_metainfo(self, task, config):
        self.do_sleep(config, 'metainfo')

    @plugin.priority(255)
    def on_task_filter(self, task, config):
        self.do_sleep(config, 'filter')

    @plugin.priority(255)
    def on_task_download(self, task, config):
        self.do_sleep(config, 'download')

    @plugin.priority(255)
    def on_task_modify(self, task, config):
        self.do_sleep(config, 'modify')

    @plugin.priority(255)
    def on_task_output(self, task, config):
        self.do_sleep(config, 'output')

    @plugin.priority(255)
    def on_task_learn(self, task, config):
        self.do_sleep(config, 'learn')

    @plugin.priority(255)
    def on_task_abort(self, task, config):
        self.do_sleep(config, 'abort')

    @plugin.priority(255)
    def on_task_exit(self, task, config):
        self.do_sleep(config, 'exit')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSleep, 'sleep', api_ver=2)
