import logging
from flexget.ui.webui import register_plugin, db_session
from flask import render_template, Module, jsonify
from flexget.plugin import DependencyError, plugins, get_plugin_by_name

log = logging.getLogger('ui.schema')
schema = Module(__name__)


@schema.route('/plugins')
def index():
    return jsonify(plugins=plugins.keys())


@schema.route('/plugin/<name>')
def plugin_schema(name):
    return jsonify( get_plugin_by_name(name).instance.validator().schema())


register_plugin(schema)