from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flask import jsonify

from flexget.db_schema import reset_schema, plugin_schemas
from flexget.api import api, APIResource

log = logging.getLogger('database')

db_api = api.namespace('database', description='Manage Flexget DB')


@db_api.route('/cleanup/')
class DBCleanup(APIResource):

    @api.response(200, 'DB Cleanup triggered')
    def get(self, session=None):
        """ Make all plugins clean un-needed data from the database """
        self.manager.db_cleanup(force=True)
        return {'status': 'success',
                'message': 'DB Cleanup triggered'}, 200


@db_api.route('/vacuum/')
class DBVacuum(APIResource):

    @api.response(200, 'DB VACUUM triggered')
    def get(self, session=None):
        """ Potentially increase performance and decrease database size"""
        session.execute('VACUUM')
        session.commit()
        return {'status': 'success',
                'message': 'DB VACUUM triggered'}, 200


plugin_parser = api.parser()
plugin_parser.add_argument('plugin_name', required=True, help='Name of plugin to reset')


@db_api.route('/reset_plugin/')
class DBPluginReset(APIResource):

    @api.response(200, 'Plugin DB reset triggered')
    @api.response(400, 'The plugin has no stored schema to reset')
    @api.doc(parser=plugin_parser)
    def get(self, session=None):
        """ Reset the DB of a specific plugin """
        args = plugin_parser.parse_args()
        plugin = args['plugin_name']
        try:
            reset_schema(plugin)
        except ValueError:
            return {'status': 'error',
                    'message': 'The plugin {} has no stored schema to reset'.format(plugin)}, 400
        return {'status': 'success',
                'message': 'Plugin {} DB reset was successful'.format(plugin)}, 200


@db_api.route('/plugins/')
class DBPluginsSchemas(APIResource):

    @api.response(200, 'Successfully retrieved a list of plugin names to reset')
    def get(self, session=None):
        """ Get a list of plugin names available to reset """
        return jsonify(list(plugin_schemas))
