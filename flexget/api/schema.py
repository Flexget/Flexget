from flask import jsonify
from flexget.api import api, APIResource
from flexget.config_schema import schema_paths, resolve_ref

schema_api = api.namespace('schema', description='Flexget JSON schema')
_plugins_cache = None


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

    def _rewrite_refs(self, schema):
        """ Used to resolve all the refs as swagger ui does not handle this properly """
        if isinstance(schema, list):
            for value in schema:
                self._rewrite_refs(value)

        if isinstance(schema, dict):
            for key, value in schema.iteritems():
                if isinstance(value, (list, dict)):
                    self._rewrite_refs(value)

            if key == '$ref' and value in schema_paths:
                del schema[key]
                schema.update(resolve_ref(value))

    def get(self, path, session=None):
        path = '/schema/%s' % path

        if path == '/schema/plugins':
            global _plugins_cache
            if not _plugins_cache:
                _plugins_cache = resolve_ref(path)
                self._rewrite_refs(_plugins_cache)
            return _plugins_cache

        if path in schema_paths:
            schema = resolve_ref(path)
            self._rewrite_refs(schema)
            return schema
        return {'error': 'invalid schema path'}, 404
