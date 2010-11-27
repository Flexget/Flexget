from flexget.webui import register_plugin
from flexget.plugin import plugins
from flask import render_template, Module

plugins_module = Module(__name__, url_prefix='/plugins')


@plugins_module.route('/')
def index():
    context = {}
    context['plugins'] = plugins
    return render_template('plugins.html', **context)

register_plugin(plugins_module, menu='Plugins')
