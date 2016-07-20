from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask_restplus import inputs

from flexget.plugin import get_plugins
from flexget.api import api, APIResource, ApiError

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

plugin_list_reply_schema = api.schema('plugin_list_reply', plugin_list_reply)

plugins_parser = api.parser()
plugins_parser.add_argument('group', help='Show plugins belonging to this group')
plugins_parser.add_argument('phase', help='Show plugins that act on this phase')
plugins_parser.add_argument('include_schema', type=inputs.boolean, default=False,
                            help='Include plugin schema. This will increase response size')


@plugins_api.route('/')
class PluginsAPI(APIResource):
    @api.response(200, model=plugin_list_reply_schema)
    @api.response(500, 'Unknown phase')
    @api.doc(parser=plugins_parser)
    def get(self, session=None):
        """ Get list of registered plugins """
        args = plugins_parser.parse_args()
        plugin_list = []
        try:
            for plugin in get_plugins(phase=args['phase'], group=args['group']):
                p = {'name': plugin.name,
                     'api_ver': plugin.api_ver,
                     'builtin': plugin.builtin,
                     'category': plugin.category,
                     'contexts': plugin.contexts,
                     'debug': plugin.debug,
                     'groups': plugin.groups}
                p['phase_handlers'] = [dict(phase=handler, priority=event.priority) for handler, event in
                                       plugin.phase_handlers.items()]

                if args['include_schema']:
                    p['schema'] = plugin.schema
                plugin_list.append(p)
        except ValueError as e:
            raise ApiError(str(e))
        return {'plugin_list': plugin_list,
                'number_of_plugins': len(plugin_list)}
