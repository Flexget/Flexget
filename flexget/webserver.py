from __future__ import unicode_literals, division, absolute_import
import logging
import os
import threading
import socket

from flask import Flask, abort, redirect, url_for

from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.utils.tools import singleton

log = logging.getLogger('web_server')

app = Flask(__name__)
_home = None
server = None

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


@app.route('/')
def start_page():
    """Redirect user to registered UI home"""
    if not _home:
        abort(404)
    return redirect(url_for(_home))


def register_home(route):
    """Registers UI home page"""
    global _home
    _home = route


@event('manager.daemon.started')
# @event('manager.config_updated') # Disabled for now
def setup_server(manager):
    """Sets up and starts/restarts the web service."""
    if not manager.is_daemon:
        return
    web_server = WebServer(manager)
    if web_server.is_alive():
        web_server.stop()
    if manager.config.get('webui'):
        web_server.start(manager.config['webui'])


@event('manager.shutdown_requested')
def stop_webui(manager):
    """Sets up and starts/restarts the webui."""
    if not manager.is_daemon:
        return
    web_server = WebServer(manager)
    if web_server.is_alive():
        web_server.stop()


@singleton
class WebServer(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, manager):
        threading.Thread.__init__(self, name='webui')
        self.daemon = True
        self.manager = manager
        self.config = {}
        self._stopped = False
        self._server = None

    def _start_server(self, bind, port=5050):
        from cherrypy import wsgiserver
        d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        self._server = wsgiserver.CherryPyWSGIServer((bind, port), d)

        log.debug('server %s' % server)
        try:
            self._server.start()
        except KeyboardInterrupt:
            self.stop()

    def start(self, config):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if self._stopped and not self.is_alive():
            self.__init__(self.manager)
        self.config = config
        threading.Thread.start(self)

    def stop(self):
        log.debug('Shutting down server')
        if self._server:
            self._server.stop()

    def run(self):
        # Start Flask
        app.secret_key = os.urandom(24)

        log.info('Starting web server on port %s' % self.config.get('port'))

        from flexget.api import api_bp
        app.register_blueprint(api_bp)

        if self.config['autoreload']:
            # Create and destroy a socket so that any exceptions are raised before
            # we spawn a separate Python interpreter and lose this ability.
            from werkzeug.serving import run_with_reloader
            reloader_interval = 1
            extra_files = None
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_socket.bind((self.config.get('bind'), self.config.get('port')))
            test_socket.close()
            log.warning('Not starting scheduler, since autoreload is enabled.')
            # TODO: run_with_reloader should not be used here
            run_with_reloader(self._start_server, extra_files, reloader_interval)
        else:
            self._start_server(self.config.get('bind'), self.config.get('port'))

        self._stopped = True
        log.debug('webui shut down')


@event('config.register')
def register_config():
    register_config_key('webui', main_schema)