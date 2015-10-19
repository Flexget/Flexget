from flask import jsonify

from flexget.api import api, APIResource
from flexget.config_schema import schema_paths, resolve_ref


schema_api = api.namespace('schema', description='Flexget JSON schema')


@schema_api.route('/')
class SchemaAllAPI(APIResource):
    def get(self, session=None):
        schemas = {}
        for path in schema_paths:
            schemas[path] = resolve_ref(path)

        return jsonify({'schemas': schemas})


@schema_api.route('/<path:path>')
@api.doc(params={'path': 'Path of schema'})
@api.response(404, 'invalid schema path')
class SchemaAPI(APIResource):

    def get(self, path, session=None):
        path = '/schema/%s' % path
        if path in schema_paths:
            return resolve_ref(path)
        return {'error': 'invalid schema path'}, 404