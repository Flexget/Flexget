from builtins import *

import logging
import socket
from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from requests.exceptions import RequestException
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = 'cronitor'

log = logging.getLogger(plugin_name)


class Cronitor(object):
    """
    Example::
      cronitor:
        monitor_code: ABC123
    """
    base_url = 'https://cronitor.link/{monitor_code}/{status}'

    schema = {
        'type': 'object',
        'properties': {
            'monitor_code': {'type': 'string'},
            'on_start': {'type': 'boolean', 'default': True},
            'on_abort': {'type': 'boolean', 'default': True},
            'message': {'type': 'string'},
            'host': {'type': 'string', 'default': socket.gethostname()},
            'auth_key': {'type': 'string'}
        },
        'required': ['monitor_code'],
        'additionalProperties': False,
    }

    def _send_request(self, config, status, task_name):
        url = self.base_url.format(monitor_code=config['monitor_code'], status=status)
        message = config.get('message', '{task} task {status}'.format(task=task_name, status=status))
        data = {
            'msg': message,
            'host': config['host'],
        }
        if config.get('auth_key'):
            data['auth_key'] = config['auth_key']
        try:
            rsp = requests.get(url, params=data)
            rsp.raise_for_status()
        except RequestException as e:
            raise PluginWarning('Could not report to cronitor: {}'.format(e))

    def on_task_start(self, task, config):
        if not config['on_start']:
            return
        self._send_request(config, 'run', task.name)

    def on_task_abort(self, task, config):
        if not config['on_abort']:
            return
        self._send_request(config, 'fail', task.name)

    def on_task_exit(self, task, config):
        self._send_request(config, 'complete', task.name)


@event('plugin.register')
def register_plugin():
    plugin.register(Cronitor, plugin_name, api_ver=2)
