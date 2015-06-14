"""
Fires events:

webui.start
  When webui is being started, this is just before WSGI server is started. Everything else is already initialized.

webui.stop
  When webui is being shut down, the WSGI server has exited the "serve forever" loop.
"""

from __future__ import unicode_literals, division, absolute_import
import logging
import os
import urllib
import socket
import sys

from flask import Flask, redirect, url_for, abort, request, send_from_directory
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.session import sessionmaker

from flexget.event import fire_event
from flexget.plugin import DependencyError
from flexget.ui.api import api, api_schema

log = logging.getLogger('webui')

app = Flask(__name__)
manager = None
db_session = None
server = None

_home = None
_menu = []


def _update_menu(root):
    """Iterates trough menu navigation and sets the item selected based on the :root:"""
    for item in _menu:
        if item['href'].startswith(root):
            item['current'] = True
            log.debug('current menu item %s' % root)
        else:
            if 'current' in item:
                item.pop('current')


@app.route('/')
def start_page():
    """Redirect user to registered home plugin"""
    if not _home:
        abort(404)
    return redirect(url_for(_home))


@app.route('/userstatic/<path:filename>')
def userstatic(filename):
    return send_from_directory(os.path.join(manager.config_base, 'userstatic'), filename)


@app.context_processor
def flexget_variables():
    path = urllib.splitquery(request.path)[0]
    root = '/' + path.split('/', 2)[1]
    # log.debug('root is: %s' % root)
    _update_menu(root)
    return {'menu': _menu, 'manager': manager}


def load_ui_plugins():

    # TODO: load from ~/.flexget/ui/plugins too (or something like that)

    import flexget.ui.plugins
    d = flexget.ui.plugins.__path__[0]

    plugin_names = set()
    for f in os.listdir(d):
        path = os.path.join(d, f, '__init__.py')
        if os.path.isfile(path):
            plugin_names.add(f)

    for name in plugin_names:
        try:
            log.info('Loading UI plugin %s' % name)
            exec "import flexget.ui.plugins.%s" % name
        except DependencyError as e:
            # plugin depends on another plugin that was not imported successfully
            log.error(e.message)
        except EnvironmentError as e:
            log.info('Plugin %s: %s' % (name, e.message))
        except Exception as e:
            log.critical('Exception while loading plugin %s' % name)
            log.exception(e)
            raise


def register_plugin(blueprint, menu=None, order=128, home=False):
    """
    Registers UI plugin.

    :plugin: :class:`flask.Blueprint` object for this plugin.
    """
    # Set up some defaults if the plugin did not already specify them
    if blueprint.url_prefix is None:
        blueprint.url_prefix = '/' + blueprint.name
    if not blueprint.template_folder and os.path.isdir(os.path.join(blueprint.root_path, 'templates')):
        blueprint.template_folder = 'templates'
    if not blueprint.static_folder and os.path.isdir(os.path.join(blueprint.root_path, 'static')):
        blueprint.static_folder = 'static'
    log.info('Registering UI plugin %s' % blueprint.name)
    app.register_blueprint(blueprint)
    if menu:
        register_menu(blueprint.url_prefix, menu, order=order)
    if home:
        register_home(blueprint.name + '.index')


def register_menu(href, caption, order=128):
    global _menu
    _menu.append({'href': href, 'caption': caption, 'order': order})
    _menu = sorted(_menu, key=lambda item: item['order'])


def register_home(route, order=128):
    """Registers homepage elements"""
    global _home
    # TODO: currently supports only one plugin
    if _home is not None:
        raise Exception('Home is already registered')
    _home = route


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Remove db_session after request"""
    db_session.remove()
    log.debug('db_session removed')


def start(mg):
    """Start WEB UI"""

    global manager
    manager = mg

    # Create sqlalchemy session for Flask usage
    global db_session
    db_session = scoped_session(sessionmaker(autocommit=False,
                                             autoflush=False,
                                             bind=manager.engine))
    if db_session is None:
        raise Exception('db_session is None')

    load_ui_plugins()

    # quick hack: since ui plugins may add tables to SQLAlchemy too and they're not initialized because create
    # was called when instantiating manager .. so we need to call it again
    from flexget.manager import Base
    Base.metadata.create_all(bind=manager.engine)

    app.register_blueprint(api)
    app.register_blueprint(api_schema)
    fire_event('webui.start')

    # Start Flask
    app.secret_key = os.urandom(24)

    set_exit_handler(stop_server)

    log.info('Starting server on port %s' % manager.options.webui.port)

    if manager.options.webui.autoreload:
        # Create and destroy a socket so that any exceptions are raised before
        # we spawn a separate Python interpreter and lose this ability.
        from werkzeug.serving import run_with_reloader
        reloader_interval = 1
        extra_files = None
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind((manager.options.webui.bind, manager.options.webui.port))
        test_socket.close()
        log.warning('Not starting scheduler, since autoreload is enabled.')
        run_with_reloader(start_server, extra_files, reloader_interval)
    else:
        start_server()

    log.debug('server exited')
    fire_event('webui.stop')
    manager.shutdown(finish_queue=False)


def start_server():
    global server
    from cherrypy import wsgiserver
    d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
    server = wsgiserver.CherryPyWSGIServer((manager.options.webui.bind, manager.options.webui.port), d)

    log.debug('server %s' % server)
    try:
        server.start()
    except KeyboardInterrupt:
        stop_server()


def stop_server(*args):
    log.debug('Shutting down server')
    if server:
        server.stop()


def set_exit_handler(func):
    """Sets a callback function for term signal on windows or linux"""
    if os.name == 'nt':
        try:
            import win32api
            win32api.SetConsoleCtrlHandler(func, True)
        except ImportError:
            version = '.'.join(map(str, sys.version_info[:2]))
            raise Exception('pywin32 not installed for Python ' + version)
    else:
        import signal
        signal.signal(signal.SIGTERM, func)
