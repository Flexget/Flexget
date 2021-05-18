from flask import jsonify, request, Response
from sqlalchemy.orm import Session

from flexget.api import APIResource, api
from flexget.api.app import BadRequest, base_message_schema, success_response
from flexget.db_schema import plugin_schemas, reset_schema

db_api = api.namespace('database', description='Manage Flexget DB')


class ObjectsContainer:
    plugin_list = {'type': 'array', 'items': {'type': 'string'}}

    database_input_object = {
        'type': 'object',
        'properties': {
            'operation': {'type': 'string', 'enum': ['cleanup', 'vacuum', 'plugin_reset']},
            'plugin_name': {'type': 'string'},
        },
        'required': ['operation'],
        'additionalProperties': False,
    }


plugins_schema = api.schema_model('plugins_list', ObjectsContainer.plugin_list)
input_schema = api.schema_model('db_schema', ObjectsContainer.database_input_object)


@db_api.route('/')
class DBOperation(APIResource):
    @api.validate(input_schema)
    @api.response(200, model=base_message_schema)
    def post(self, session: Session = None) -> Response:
        """Perform DB operations"""
        msg = ''
        data = request.json
        operation = data['operation']
        if operation == 'cleanup':
            self.manager.db_cleanup(force=True)
            msg = 'DB Cleanup finished'
        elif operation == 'vacuum':
            session.execute('VACUUM')
            session.commit()
            msg = 'DB VACUUM finished'
        elif operation == 'plugin_reset':
            plugin_name = data.get('plugin_name')
            if not plugin_name:
                raise BadRequest(
                    "'plugin_name' attribute must be used when trying to reset plugin"
                )
            try:
                reset_schema(plugin_name)
                msg = f'Plugin {plugin_name} DB reset was successful'
            except ValueError:
                raise BadRequest(f'The plugin {plugin_name} has no stored schema to reset')
        return success_response(msg)


@db_api.route('/plugins/')
class DBCleanup(APIResource):
    @api.response(200, model=plugins_schema)
    def get(self, session: Session = None) -> Response:
        """List resettable DB plugins"""
        return jsonify(sorted(list(plugin_schemas)))
