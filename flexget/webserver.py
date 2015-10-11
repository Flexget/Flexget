from __future__ import unicode_literals, division, absolute_import
import logging
import os
import threading

from flask import Flask, abort, redirect

from flexget.event import event
from flexget.config_schema import register_config_key
from flexget.utils.tools import singleton

log = logging.getLogger('web_server')

_home = None
_app_register = {}
_default_app = Flask(__name__)

app = None

web_config_schema = {
    'oneOf': [
        {'type': 'boolean'},
        {
            'type': 'object',
            'properties': {
                'bind': {'type': 'string', 'format': 'ipv4', 'default': '0.0.0.0'},
                'port': {'type': 'integer', 'default': 5050},
            },
            'additionalProperties': False
        }
    ]
}


@event('config.register')
def register_config():
    register_config_key('web_server', web_config_schema)


def register_app(path, application):
    if path in _app_register:
        raise ValueError('path %s already registered')
    _app_register[path] = application


def register_home(route):
    """Registers UI home page"""
    global _home
    _home = route


@_default_app.route('/')
def start_page():
    """ Redirect user to registered UI home """
    if not _home:
        abort(404)
    return redirect(_home)


@event('manager.daemon.started', -255)  # Low priority so plugins can register apps
def setup_server(manager):
    """ Sets up and starts/restarts the web service. """
    if not manager.is_daemon:
        return

    web_server_config = manager.config.get('web_server')

    if not web_server_config:
        return

    web_server = WebServer(
        bind=web_server_config['bind'],
        port=web_server_config['port'],
    )

    if web_server.is_alive():
        web_server.stop()

    if _app_register:
        web_server.start()


@event('manager.shutdown_requested')
def stop_server(manager):
    """ Sets up and starts/restarts the webui. """
    if not manager.is_daemon:
        return
    web_server = WebServer()
    if web_server.is_alive():
        web_server.stop()


@singleton
class WebServer(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, bind='0.0.0.0', port=5050):
        threading.Thread.__init__(self, name='web_server')
        self.bind = str(bind)  # String to remove unicode warning from cherrypy startup
        self.port = port
        self.server = None

    def start(self):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if not self.is_alive():
            self.__init__(bind=self.bind, port=self.port)
        threading.Thread.start(self)

    def _start_server(self):
        from cherrypy import wsgiserver

        apps = {'/': _default_app}
        for path, registered_app in _app_register.iteritems():
            apps[path] = registered_app

        d = wsgiserver.WSGIPathInfoDispatcher(apps)
        self.server = wsgiserver.CherryPyWSGIServer((self.bind, self.port), d)
        self.server.start()

    def run(self):
        _default_app.secret_key = os.urandom(24)

        log.info('Starting web server on port %s' % self.port)
        self._start_server()

    def stop(self):
        log.info('Shutting down web server')
        if self.server:
            self.server.stop()
