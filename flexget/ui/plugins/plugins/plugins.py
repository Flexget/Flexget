from flexget.ui.webui import register_plugin, manager
from flexget.plugin import plugins
from flask import render_template, Module

plugins_module = Module(__name__, url_prefix='/plugins')


@plugins_module.route('/')
def index():
    context = {'plugins': plugins}
    return render_template('plugins/plugins.html', **context)


if manager.options.debug:
    register_plugin(plugins_module, menu='Plugins (DEV)')
