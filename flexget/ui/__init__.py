from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os
import fnmatch

from flask import send_from_directory, Flask

from flexget.webserver import register_app, register_home
from flask_compress import Compress

log = logging.getLogger('webui')

manager = None
debug = False
app_base = None

ui_base = os.path.dirname(os.path.realpath(__file__))
ui_src = os.path.join(ui_base, 'src')
ui_dist = os.path.join(ui_base, 'app')
bower_components = os.path.join(ui_base, 'bower_components')

webui_app = Flask(__name__)
Compress(webui_app)
webui_app.url_path = '/'


@webui_app.route('/<path:path>')
def serve_app(path):
    if debug:
        if path.startswith('bower_components'):
            return send_from_directory(bower_components, path.lstrip('bower_components').lstrip('/'))

        if os.path.exists(os.path.join(ui_src, path)):
            return send_from_directory(ui_src, path)

    return send_from_directory(app_base, path)


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


def _strip_trailing_sep(path):
    return path.rstrip('\\/')


def register_web_ui(mgr):
    global manager, app_base, debug
    manager = mgr

    if 'debug' in manager.args:
        debug = True

    if debug:
        app_base = os.path.join(ui_base, '.tmp', 'serve')
        if not os.path.exists(app_base):
            log.warning('Unable to start web ui in debug mode. To enable debug mode please run the debug build, '
                        'see http://flexget.com/wiki/Web-UI for instructions')
            log.warning('Attempting to serve web ui from complied directory')
            app_base = None

    if not app_base:
        app_base = ui_dist
        if not os.path.exists(app_base):
            log.fatal('Failed to start web ui,'
                      ' this can happen if you are running from GitHub version and forgot to run the web ui build, '
                      'see http://flexget.com/wiki/Web-UI for instructions')

            app_base = None

    register_app(webui_app.url_path, webui_app)
    register_home('%s/' % webui_app.url_path)
