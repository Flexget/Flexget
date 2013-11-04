from __future__ import unicode_literals, division, absolute_import
from flask import Blueprint, jsonify
from flexget.ui.webui import register_plugin
from flexget.plugin import plugins, get_plugins, task_phases, plugin_contexts

plugins_module = Blueprint('plugins', __name__)


def plugin_infos(plugins):
    def plugin_info(plugin):
        return {'contexts': plugin.contexts,
                'groups': plugin.groups,
                'category': plugin.category}

    return dict((p.name, plugin_info(p)) for p in plugins)


# JSON API
@plugins_module.route('/all')
def all_plugins():
    return jsonify(plugins=plugin_infos(plugins.itervalues()))


@plugins_module.route('/phases')
def phases():
    return jsonify(phases=task_phases)


@plugins_module.route('/phase/<phase>')
def plugins_by_phase(phase):
    try:
        return jsonify(plugins=plugin_infos(get_plugins(phase=phase)))
    except Exception as e:
        return e.message, 404


@plugins_module.route('/groups')
def groups():
    # TODO: There should probably be a function in plugin.py to get this
    groups = set()
    for plugin in plugins.itervalues():
        groups.update(plugin.get('groups'))
    return jsonify(groups=list(groups))


@plugins_module.route('/group/<group>')
def plugins_by_group(group):
    return jsonify(plugins=plugin_infos(get_plugins(group=group)))


@plugins_module.route('/contexts')
def contexts():
    return jsonify(contexts=plugin_contexts)


@plugins_module.route('/context/<context>')
def plugins_by_context(context):
    return jsonify(plugins=plugin_infos(get_plugins(context=context)))


@plugins_module.route('/categories')
def categories():
    # TODO: Should this only return the list of categories that actually have plugins?
    return jsonify(categories=task_phases)


@plugins_module.route('/category/<category>')
def plugins_by_category(category):
    return jsonify(plugins=plugin_infos(get_plugins(category=category)))


register_plugin(plugins_module)
