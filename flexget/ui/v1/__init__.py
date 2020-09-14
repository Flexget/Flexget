import fnmatch
import os

from flask import Flask, redirect, request, send_from_directory
from flask_compress import Compress
from loguru import logger

from flexget.webserver import register_app, register_home

logger = logger.bind(name='webui')

manager = None
debug = False
app_base = None

ui_base = os.path.dirname(os.path.realpath(__file__))
ui_src = os.path.join(ui_base, 'src')
ui_dist = os.path.join(ui_base, 'app')
bower_components = os.path.join(ui_base, 'bower_components')

webui_app = Flask(__name__)
Compress(webui_app)
webui_app.url_path = '/v1/'

HTTP_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH']


@webui_app.route('/<path:path>')
def serve_app(path):
    if debug:
        if path.startswith('bower_components'):
            return send_from_directory(
                bower_components, path.lstrip('bower_components').lstrip('/')
            )

        if os.path.exists(os.path.join(ui_src, path)):
            return send_from_directory(ui_src, path)

    if not app_base:
        return send_from_directory(ui_base, 'load.failure.html')

    return send_from_directory(app_base, path)


@webui_app.route('/api/')
@webui_app.route('/api/<path:path>', methods=HTTP_METHODS)
def api_redirect(path='/'):
    return redirect(request.url.replace('/v1', '', 1), 307)


@webui_app.route('/')
def root():
    if not app_base:
        return send_from_directory(ui_base, 'load.failure.html')

    return send_from_directory(app_base, 'app.html')


def _find(path, f):
    matches = []
    for root_dir, _, file_names in os.walk(path):
        for filename in fnmatch.filter(file_names, f):
            matches.append(os.path.join(root_dir, filename))
    return matches


def register_web_ui(mgr):
    global manager, app_base, debug
    manager = mgr

    if 'debug' in manager.args:
        debug = True

    if debug:
        app_base = os.path.join(ui_base, '.tmp', 'serve')
        if not os.path.exists(app_base):
            logger.warning(
                'Unable to start web ui in debug mode. To enable debug mode please run the debug build, '
                'see http://flexget.com/wiki/Web-UI for instructions'
            )
            logger.warning('Attempting to serve web ui from complied directory')
            app_base = None

    if not app_base:
        app_base = ui_dist
        if not os.path.exists(app_base):
            logger.critical(
                'Failed to start web ui,'
                ' this can happen if you are running from GitHub version and forgot to run the web ui build, '
                'see http://flexget.com/wiki/Web-UI for instructions'
            )
            app_base = None

    register_app(webui_app.url_path, webui_app, 'WebUI (v1)')
    register_home('%s/' % webui_app.url_path)
