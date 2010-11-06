from flexget.webui import register_plugin
from flask import render_template, Module

log = Module(__name__)


@log.route('/')
def index():
    return render_template('log.html')


register_plugin(log, menu='Log', order=256)
