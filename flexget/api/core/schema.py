from flask import jsonify, request
from jsonschema import RefResolutionError

from flexget.api import APIResource, api
from flexget.api.app import NotFoundError
from flexget.config_schema import resolve_ref, schema_paths

schema_api = api.namespace('schema', description='Config and plugin schemas')

schema_api_list = api.schema_model(
    'schema.list',
    {'type': 'object', 'properties': {'schemas': {'type': 'array', 'items': {'type': 'object'}}}},
)


@schema_api.route('/')
class SchemaAllAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, session=None):
        """ List all schema definitions """
        schemas = {}
        for path in schema_paths:
            schemas[path] = resolve_ref(path)

        return jsonify({'schemas': schemas})


@schema_api.route('/<path:path>/')
@api.doc(params={'path': 'Path of schema'})
@api.response(NotFoundError)
class SchemaAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, path, session=None):
        """ Get schema definition """
        path = f'/schema/{path}'
        if request.query_string:
            path += '?' + request.query_string.decode('ascii')
        try:
            return jsonify(resolve_ref(path))
        except RefResolutionError:
            raise NotFoundError('invalid schema path')
