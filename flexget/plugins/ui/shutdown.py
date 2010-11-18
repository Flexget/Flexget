from flexget.webui import register_plugin
from flask import render_template, Module

import logging

shutdown = Module(__name__, url_prefix='/shutdown')

log = logging.getLogger('shutdown')


@shutdown.route('/')
def index():
    return render_template('shutdown.html')


@shutdown.route('/now')
def now():
    raise NotImplementedError


register_plugin(shutdown, menu='Shutdown', order=512)
