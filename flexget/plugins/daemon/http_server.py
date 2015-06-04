from __future__ import unicode_literals, division, absolute_import
import logging
import threading

from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.utils.tools import singleton

log = logging.getLogger('webui')

main_schema = {
    'type': 'object',
    'properties': {
        'bind': {'type': 'string', 'format': 'ipv4', 'default': '0.0.0.0'},
        'port': {'type': 'integer', 'default': 5050},
        'autoreload': {'type': 'boolean', 'default': False},
        'authentication': {
            'oneOf': [
                {"type": "boolean"},
                {
                    "type": "object",
                    "properties": {
                        'username': {'type': 'string'},
                        'password': {'type': 'string'},
                        'no_local_auth': {'type': 'boolean', 'default': True}
                    },
                    'additionalProperties': False
                }
            ],
        },
    },
    'additionalProperties': False
}


@event('manager.daemon.started')
# @event('manager.config_updated') # Disabled for now
def setup_webui(manager):
    """Sets up and starts/restarts the webui."""
    if not manager.is_daemon:
        return
    webui = HTTPServer(manager)
    if webui.is_alive():
        webui.stop()
    if manager.config.get('webui'):
        webui.start(manager.config['webui'])


@event('manager.shutdown_requested')
def stop_webui(manager):
    """Sets up and starts/restarts the webui."""
    if not manager.is_daemon:
        return
    webui = HTTPServer(manager)
    if webui.is_alive():
        webui.stop()


@singleton
class HTTPServer(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, manager):
        threading.Thread.__init__(self, name='webui')
        self.daemon = True
        self.manager = manager
        self.config = {}
        self._stopped = False

    def start(self, config):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if self._stopped and not self.is_alive():
            self.__init__(self.manager)
        self.config = config
        threading.Thread.start(self)

    def stop(self):
        from flexget.ui.webui import stop_server
        stop_server()

    def run(self):
        from flexget.ui.webui import start
        log.debug('webui starting')
        start(self.manager)
        self._stopped = True
        log.debug('webui shut down')


@event('config.register')
def register_config():
    register_config_key('webui', main_schema)