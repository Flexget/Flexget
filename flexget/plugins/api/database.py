from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask import request
from flask_restplus import inputs

from flexget.manager import Base
from flexget.db_schema import reset_schema
from flexget.api import api, APIResource, NotFoundError, ApiError

log = logging.getLogger('database')

db_api = api.namespace('database', description='Manage Flexget DB')


@db_api.route('/cleanup/')
@api.doc(description='Make all plugins clean un-needed data from the database')
class DBCleanup(APIResource):
    @api.response(200, 'DB Cleanup triggered')
    def get(self, session=None):
        self.manager.db_cleanup(force=True)
        return {'status': 'success',
                'message': 'DB Cleanup triggered'}, 200


@db_api.route('/vacuum/')
@api.doc(description='Running vacuum can increase performance and decrease database size')
class DBVacuum(APIResource):
    @api.response(200, 'DB VACUUM triggered')
    def get(self, session=None):
        session.execute('VACUUM')
        session.commit()
        return {'status': 'success',
                'message': 'DB VACUUM triggered'}, 200


reset_parser = api.parser()
reset_parser.add_argument('sure', type=inputs.boolean, default='false', required=True,
                          help='You must use this flag to indicate you REALLY want to do this')

plugin_parser = api.parser()
plugin_parser.add_argument('plugin_name', required=True, help='Name of plugin to reset')


@db_api.route('/reset_plugin/')
class DBPluginReset(APIResource):
    @api.response(200, 'Plugin DB reset triggered')
    @api.response(500, 'The plugin has no stored schema to reset')
    @api.doc(parser=plugin_parser)
    def get(self, session=None):
        args = plugin_parser.parse_args()
        plugin = args['plugin_name']
        try:
            reset_schema(plugin)
        except ValueError:
            return {'status': 'error',
                    'message': 'The plugin {} has no stored schema to reset'.format(plugin)}, 400
        return {'status': 'success',
                'message': 'Plugin {} DB reset was successful'.format(plugin)}, 200
