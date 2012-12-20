from __future__ import unicode_literals, division, absolute_import
from flexget.ui.webui import register_plugin, stop_server
from flask import render_template, Module

import logging

shutdown = Module(__name__, url_prefix='/shutdown')

log = logging.getLogger('shutdown')


@shutdown.route('/')
def index():
    return render_template('shutdown/shutdown.html')


@shutdown.route('/now')
def now():
    stop_server()
    return 'Shutdown Complete'


register_plugin(shutdown, menu='Shutdown', order=512)
