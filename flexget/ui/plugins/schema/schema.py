import logging
from flexget.ui.webui import register_plugin
from flask import Module, jsonify
from flexget.plugin import (DependencyError, plugins, get_plugin_by_name, get_plugins_by_phase, get_plugins_by_group,
                            task_phases)

log = logging.getLogger('ui.schema')
schema = Module(__name__)


@schema.route('/plugins')
def get_plugins():
    return jsonify(plugins=plugins.keys())


@schema.route('/plugins/phases')
def phases():
    return jsonify(phases=task_phases)


@schema.route('/plugins/phase/<phase>')
def plugins_by_phase(phase):
    try:
        return jsonify(plugins=[plugin.name for plugin in get_plugins_by_phase(phase)])
    except Exception, e:
        return e.message, 404


@schema.route('/plugins/groups')
def groups():
    # TODO: There should probably be a function in plugin.py to get this
    groups = set()
    for plugin in plugins.itervalues():
        groups.update(plugin.get('groups'))
    return jsonify(groups=list(groups))


@schema.route('/plugins/group/<group>')
def plugins_by_group(group):
    return jsonify(plugins=[plugin.name for plugin in get_plugins_by_group(group)])


@schema.route('/plugin/<name>')
def plugin_schema(name):
    try:
        plugin = get_plugin_by_name(name).instance
    except DependencyError:
        return 'Plugin %s does not exist' % name, 404
    try:
        validator = plugin.validator()
    except AttributeError:
        return 'Plugin %s does not have a schema' % name, 404
    return jsonify(validator.schema())


register_plugin(schema)