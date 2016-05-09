from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flask import jsonify, request
from jsonschema import RefResolutionError

from flexget.api import api, APIResource
from flexget.config_schema import schema_paths, resolve_ref

schema_api = api.namespace('schema', description='Config and plugin schemas')
_plugins_cache = None

schema_api_list = api.schema('schema.list', {
    'type': 'object',
    'properties': {
        'schemas': {
            'type': 'array',
            'items': {'type': 'object'}
        }
    }
})


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
@api.response(404, 'invalid schema path')
class SchemaAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, path, session=None):
        """ Get schema definition """
        path = '/schema/%s' % path
        if request.query_string:
            path += '?' + request.query_string
        try:
            return resolve_ref(path)
        except RefResolutionError:
            return {'error': 'invalid schema path'}, 404
