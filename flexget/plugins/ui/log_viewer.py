from flexget.webui import register_plugin
from flask import render_template, Module

log_viewer = Module(__name__)


@log_viewer.route('/')
def index():
    return render_template('log.html')


register_plugin(log_viewer, url_prefix='/log', menu='Log', order=256)
