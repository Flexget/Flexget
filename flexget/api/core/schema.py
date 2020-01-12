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


def rewrite_refs(schema, base_url):
    """
    Make sure any $refs in the schema point properly back to this endpoint.

    The refs in the schemas are arbitrary identifiers, and cannot quite be used as-is as real network locations.
    This rewrites any of those arbitrary refs to be real urls servable by this endpoint.
    """
    if isinstance(schema, dict):
        if '$ref' in schema and schema['$ref'].startswith('/schema/'):
            return {'$ref': base_url + schema['$ref'][8:]}
        return {k: rewrite_refs(v, base_url) for k, v in schema.items()}
    if isinstance(schema, list):
        return [rewrite_refs(v, base_url) for v in schema]
    return schema


@schema_api.route('/')
class SchemaAllAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, session=None):
        """ List all schema definitions """
        schemas = {}
        for path in schema_paths:
            schemas[path] = rewrite_refs(resolve_ref(path), request.base_url)
        return jsonify({'schemas': schemas})


@schema_api.route('/<path:path>/')
@api.doc(params={'path': 'Path of schema'})
@api.response(NotFoundError)
class SchemaAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, path, session=None):
        """ Get schema definition """
        try:
            return jsonify(rewrite_refs(resolve_ref(request.full_path), request.base_url))
        except RefResolutionError:
            raise NotFoundError('invalid schema path')
