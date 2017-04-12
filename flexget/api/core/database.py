from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flask import jsonify

from flexget.db_schema import reset_schema, plugin_schemas
from flexget.api import api, APIResource
from flexget.api.app import base_message_schema, success_response, BadRequest, etag

log = logging.getLogger('database')

db_api = api.namespace('database', description='Manage Flexget DB')


class ObjectsContainer(object):
    plugin_list = {'type': 'array', 'items': {'type': 'string'}}


plugins_schema = api.schema('plugins_list', ObjectsContainer.plugin_list)


@db_api.route('/cleanup/')
class DBCleanup(APIResource):
    @etag
    @api.response(200, model=base_message_schema)
    def get(self, session=None):
        """ Make all plugins clean un-needed data from the database """
        self.manager.db_cleanup(force=True)
        return success_response('DB Cleanup finished')


@db_api.route('/vacuum/')
class DBVacuum(APIResource):
    @etag
    @api.response(200, model=base_message_schema)
    def get(self, session=None):
        """ Potentially increase performance and decrease database size"""
        session.execute('VACUUM')
        session.commit()
        return success_response('DB VACUUM finished')


plugin_parser = api.parser()
plugin_parser.add_argument('plugin_name', required=True, help='Name of plugin to reset')


@db_api.route('/reset_plugin/')
class DBPluginReset(APIResource):
    @etag
    @api.response(200, model=base_message_schema)
    @api.response(BadRequest)
    @api.doc(parser=plugin_parser)
    def get(self, session=None):
        """ Reset the DB of a specific plugin """
        args = plugin_parser.parse_args()
        plugin = args['plugin_name']
        try:
            reset_schema(plugin)
        except ValueError:
            raise BadRequest('The plugin {} has no stored schema to reset'.format(plugin))
        return success_response('Plugin {} DB reset was successful'.format(plugin))


@db_api.route('/plugins/')
class DBPluginsSchemas(APIResource):
    @etag
    @api.response(200, model=plugins_schema)
    def get(self, session=None):
        """ Get a list of plugin names available to reset """
        return jsonify(sorted(list(plugin_schemas)))
