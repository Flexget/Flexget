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
ui_dist = os.path.join(ui_base, 'dist')

webui_app = Flask(__name__)
Compress(webui_app)
webui_app.url_path = '/'


@webui_app.route('/<path:path>')
def serve_app(path):
    return send_from_directory(app_base, path)


@webui_app.route('/')
def root():
    return send_from_directory(app_base, 'index.html')

def register_web_ui(mgr):
    global manager, app_base, debug
    manager = mgr

    if not app_base:
        app_base = ui_dist
        if not os.path.exists(app_base):
            log.fatal('Failed to start web ui,'
                      ' this can happen if you are running from GitHub version and forgot to run the web ui build, '
                      'see http://flexget.com/wiki/Web-UI for instructions')

            app_base = None

    register_app(webui_app.url_path, webui_app)
    register_home('%s/' % webui_app.url_path)
