from __future__ import unicode_literals, division, absolute_import
import logging
import os
import threading
import socket

from flask import Flask, abort, redirect, url_for
from werkzeug.wsgi import DispatcherMiddleware

from flexget.event import event
from flexget.utils.tools import singleton

log = logging.getLogger('web_server')

server = None

_home = None
_app_register = {}
_default_app = Flask(__name__)
_server_port = None
_server_bind = None

app = None


def register_app(path, app, bind=None, port=None):
    if path in _app_register:
        raise ValueError('path %s already registered')
    global _server_port, _server_bind
    if bind:
        if _server_bind and _server_bind != bind:
            raise ValueError('web server port already bound to %s' % _server_bind)
        _server_bind = bind
    if port:
        if _server_port and _server_port != port:
            raise ValueError('web server port already registered on %s' % _server_port)
        _server_port = port
    _app_register[path] = app


def register_home(route):
    """Registers UI home page"""
    global _home
    _home = route


@_default_app.route('/')
def start_page():
    """ Redirect user to registered UI home """
    if not _home:
        abort(404)
    return redirect(url_for(_home))


# Low priority so plugins can register apps
@event('manager.daemon.started', -255)
@event('manager.config_updated')
def setup_server(manager):
    """ Sets up and starts/restarts the web service. """
    if not manager.is_daemon:
        return

    web_server = WebServer(manager)
    if web_server.is_alive():
        web_server.stop()

    if _app_register:
        global app
        app = DispatcherMiddleware(_default_app, _app_register)
        web_server.start(bind=_server_bind, port=_server_port)


@event('manager.shutdown_requested')
def stop_server(manager):
    """ Sets up and starts/restarts the webui. """
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
        self._stopped = False
        self._server = None
        self.bind = '0.0.0.0'
        self.port = 5050
        self.autoreload = False

    def _start_server(self, bind, port=5050):
        from cherrypy import wsgiserver
        d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        self._server = wsgiserver.CherryPyWSGIServer((bind, port), d)

        log.debug('server %s' % server)
        try:
            self._server.start()
        except KeyboardInterrupt:
            self.stop()

    def start(self, bind='0.0.0.0', port=5050):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if bind:
            self.bind = bind
        if port:
            self.port = port

        if self._stopped and not self.is_alive():
            self.__init__(self.manager)
        threading.Thread.start(self)

    def stop(self):
        log.debug('Shutting down server')
        if self._server:
            self._server.stop()

    def run(self):
        # Start Flask
        _default_app.secret_key = os.urandom(24)

        log.info('Starting web server on port %s' % self.port)

        if self.autoreload:
            # TODO: Broken, fix
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
            self._start_server(self.bind, self.port)

        self._stopped = True
        log.debug('webui shut down')


