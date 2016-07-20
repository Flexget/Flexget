from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask import jsonify
from flask_restplus import inputs

from flexget.plugin import get_plugins
from flexget.api import api, APIResource, ApiError

log = logging.getLogger('plugins')

plugins_api = api.namespace('plugins', description='Get Flexget plugins')

plugins_parser = api.parser()
plugins_parser.add_argument('group', help='Show plugins belonging to this group')
plugins_parser.add_argument('phase', help='Show plugins that act on this phase')
plugins_parser.add_argument('include_schema', type=inputs.boolean, default=False,
                            help='Include plugin schema. This will increase response size')


@plugins_api.route('/')
class PluginsAPI(APIResource):
    @api.response(200, 'Successfully retrieved plugin list')
    @api.response(500, 'Unknown phase')
    @api.doc(parser=plugins_parser)
    def get(self, session=None):
        """ Get list of plugins """
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
        return jsonify(plugin_list)
