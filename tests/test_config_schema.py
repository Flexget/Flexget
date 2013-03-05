from __future__ import unicode_literals, division, absolute_import

import jsonschema

from flexget import config_schema
from tests import FlexGetBase


def iter_registered_schemas():
    for path in config_schema.schema_paths:
        schema = config_schema.resolve_ref(path)
        yield path, schema


class TestSchemaValidator(FlexGetBase):
    def test_registered_schemas_are_valid(self):
        for path, schema in iter_registered_schemas():
            try:
                config_schema.SchemaValidator.check_schema(schema)
            except jsonschema.SchemaError as e:
                assert False, 'plugin `%s` has an invalid schema. %s %s' % (
                    path, '/'.join(str(p) for p in e.path), e.message)

    def test_refs_in_schemas_are_resolvable(self):
        def check_dict(path, schema):
            for key, value in schema.iteritems():
                if key == '$ref':
                    if value.startswith('#'):
                        # Don't check in schema refs
                        continue
                    try:
                        config_schema.resolve_ref(value)
                    except jsonschema.RefResolutionError:
                        assert False, '$ref %s in schema %s is invalid' % (value, path)
                elif isinstance(value, dict):
                    check_dict(path, value)
                elif isinstance(value, list):
                    check_list(path, value)

        def check_list(path, thelist):
            for item in thelist:
                if isinstance(item, dict):
                    check_dict(path, item)
                elif isinstance(item, list):
                    check_list(path, item)

        for path, schema in iter_registered_schemas():
            check_dict(path, schema)

    def test_resolves_local_refs(self):
        schema = {'$ref': '/schema/plugin/accept_all'}
        v = config_schema.SchemaValidator(schema)
        # accept_all schema should be for type boolean
        assert v.is_valid(True)
        assert not v.is_valid(14)

    def test_custom_format_checker(self):
        schema = {'type': 'string', 'format': 'quality'}
        v = config_schema.SchemaValidator(schema)
        assert v.is_valid('720p')
        assert not v.is_valid('aoeu')
