from flask import Response, jsonify, request
from jsonschema import RefResolutionError
from sqlalchemy.orm import Session

from flexget.api import APIResource, api
from flexget.api.app import NotFoundError
from flexget.config_schema import resolve_ref, schema_paths

schema_api = api.namespace('schema', description='Config and plugin schemas')

schema_api_list = api.schema_model(
    'schema.list',
    {'type': 'object', 'properties': {'schemas': {'type': 'array', 'items': {'type': 'object'}}}},
)


def rewrite_ref(identifier: str, base_url: str) -> str:
    """
    The refs in the schemas are arbitrary identifiers, and cannot be used as-is as real network locations.
    This rewrites any of those arbitrary refs to be real urls servable by this endpoint.
    """
    if not base_url.endswith('/'):
        base_url += '/'
    if identifier.startswith('/schema/'):
        return base_url + identifier[1:]
    return identifier


def rewrite_refs(schema, base_url: str):
    """Make sure any $refs in the schema point properly back to this endpoint."""
    if isinstance(schema, dict):
        if '$ref' in schema:
            return {'$ref': rewrite_ref(schema['$ref'], base_url)}
        return {k: rewrite_refs(v, base_url) for k, v in schema.items()}
    if isinstance(schema, list):
        return [rewrite_refs(v, base_url) for v in schema]
    return schema


@schema_api.route('/')
class SchemaAllAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, session: Session = None) -> Response:
        """List all schema definitions"""
        schemas = []
        for path in schema_paths:
            schema = rewrite_refs(resolve_ref(path), request.url_root)
            schema['id'] = rewrite_ref(path, request.url_root)
            schemas.append(schema)
        return jsonify({'schemas': schemas})


@schema_api.route('/<path:path>/')
@api.doc(params={'path': 'Path of schema'})
@api.response(NotFoundError)
class SchemaAPI(APIResource):
    @api.response(200, model=schema_api_list)
    def get(self, path: str, session: Session = None) -> Response:
        """Get schema definition"""
        try:
            schema = resolve_ref(request.full_path)
        except RefResolutionError:
            raise NotFoundError('invalid schema path')
        schema['id'] = request.url
        return jsonify(rewrite_refs(schema, request.url_root))
