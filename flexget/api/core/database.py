from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flask import jsonify, request

from flexget.db_schema import reset_schema, plugin_schemas
from flexget.api import api, APIResource
from flexget.api.app import base_message_schema, success_response, BadRequest, etag

log = logging.getLogger('database')

db_api = api.namespace('database', description='Manage Flexget DB')


class ObjectsContainer(object):
    plugin_list = {'type': 'array', 'items': {'type': 'string'}}

    database_input_object = {
        'type': 'object',
        'properties': {
            'operation': {'type': 'string', 'enum': ['cleanup', 'vacuum', 'list_plugins', 'plugin_reset']}
        },
        'required': ['operation_name'],
        'additionalProperties': False
    }

    reset_plugin_input = database_input_object.copy()
    reset_plugin_input['properties']['plugin_name'] = {'type': 'string'}


plugins_schema = api.schema('plugins_list', ObjectsContainer.plugin_list)
input_schema = api.schema('db_schema', ObjectsContainer.database_input_object)
reset_plugin_input_schema = api.schema('db_schema', ObjectsContainer.reset_plugin_input)


@db_api.route('/')
class DBOperation(APIResource):
    @api.response(200, model=base_message_schema)
    def post(self, session=None):
        data = request.json
        operation = data['operation']
        if operation == 'cleanup':
            self.manager.db_cleanup(force=True)
            msg = 'DB Cleanup finished'
        elif operation == 'vacuum':
            session.execute('VACUUM')
            session.commit()
            msg = 'DB VACUUM finished'
        elif operation == 'list_plugins':
            return jsonify(sorted(list(plugin_schemas)))
        elif operation == 'plugin_reset':
            plugin_name = data['plugin_name']
            try:
                reset_schema(plugin_name)
                msg = 'Plugin {} DB reset was successful'.format(plugin_name)
            except ValueError:
                raise BadRequest('The plugin {} has no stored schema to reset'.format(plugin_name))
        return success_response(msg)


@db_api.route('/cleanup/')
class DBCleanup(APIResource):
    @api.response(200, model=base_message_schema)
    def post(self, session=None):
        """ Make all plugins clean un-needed data from the database """
        self.manager.db_cleanup(force=True)
        return success_response('DB Cleanup finished')
