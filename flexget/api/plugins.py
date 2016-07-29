from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask_restplus import inputs

from flexget.plugin import get_plugins, get_plugin_by_name, DependencyError
from flexget.api import api, APIResource, BadRequest

log = logging.getLogger('plugins')

plugins_api = api.namespace('plugins', description='Get Flexget plugins')

phase_object = {
    'type': 'object',
    'properties': {
        'phase': {'type': 'string'},
        'priority': {'type': 'integer'}
    }
}

plugin_object = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'api_ver': {'type': 'integer'},
        'builtin': {'type': 'boolean'},
        'category': {'type': 'string'},
        'contexts': {'type': 'array', 'items': {'type': 'string'}},
        'debug': {'type': 'boolean'},
        'groups': {'type': 'array', 'items': {'type': 'string'}},
        'phase_handlers': {'type': 'array', 'items': phase_object}
    }
}

plugin_list_reply = {
    'type': 'object',
    'properties': {
        'plugin_list': {'type': 'array', 'items': plugin_object},
        'number_of_plugins': {'type': 'integer'}
    }
}
plugin_schema = api.schema('plugin_object', plugin_object)
plugin_list_reply_schema = api.schema('plugin_list_reply', plugin_list_reply)

plugin_parser = api.parser()
plugin_parser.add_argument('include_schema', type=inputs.boolean, default=False,
                           help='Include plugin schema. This will increase response size')

plugins_parser = plugin_parser.copy()

plugins_parser.add_argument('group', case_sensitive=False, help='Show plugins belonging to this group')
plugins_parser.add_argument('phase', case_sensitive=False, help='Show plugins that act on this phase')


def plugin_to_dict(plugin):
    """ Returns a dict for API usage from a PluginInfo object
    :param plugin: PluginInfo instance
    :return: Dict
    """
    return {
        'name': plugin.name,
        'api_ver': plugin.api_ver,
        'builtin': plugin.builtin,
        'category': plugin.category,
        'contexts': plugin.contexts,
        'debug': plugin.debug,
        'groups': plugin.groups,
        'phase_handlers': [dict(phase=handler, priority=event.priority) for handler, event in
                           plugin.phase_handlers.items()]
    }


@plugins_api.route('/')
class PluginsAPI(APIResource):
    @api.response(200, model=plugin_list_reply_schema)
    @api.response(BadRequest)
    @api.doc(parser=plugins_parser)
    def get(self, session=None):
        """ Get list of registered plugins """
        args = plugins_parser.parse_args()
        plugin_list = []
        try:
            for plugin in get_plugins(phase=args['phase'], group=args['group']):
                p = plugin_to_dict(plugin)
                if args['include_schema']:
                    p['schema'] = plugin.schema
                plugin_list.append(p)
        except ValueError as e:
            raise BadRequest(str(e))
        return {'plugin_list': plugin_list,
                'number_of_plugins': len(plugin_list)}


@plugins_api.route('/<string:plugin_name>/')
class PluginAPI(APIResource):
    @api.response(BadRequest)
    @api.response(200, model=plugin_schema)
    @api.doc(parser=plugin_parser, params={'plugin_name': 'Name of the plugin to return'})
    def get(self, plugin_name, session=None):
        """ Return plugin data by name"""
        args = plugin_parser.parse_args()
        try:
            plugin = get_plugin_by_name(plugin_name, issued_by='plugins API')
        except DependencyError as e:
            raise BadRequest(e.message)
        p = plugin_to_dict(plugin)
        if args['include_schema']:
            p['schema'] = plugin.schema
        return p
