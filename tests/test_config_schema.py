from __future__ import unicode_literals, division, absolute_import

import jsonschema
import mock

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
                assert False, 'plugin `%s` has an invalid schema. %s %s %s' % (
                    path, '/'.join(str(p) for p in e.path), e.validator, e.message)

    def test_refs_in_schemas_are_resolvable(self):
        def refs_in(item):
            if isinstance(item, dict):
                for key, value in item.iteritems():
                    if key == '$ref':
                        yield value
                    else:
                        for ref in refs_in(value):
                            yield ref
            elif isinstance(item, list):
                for i in item:
                    for ref in refs_in(i):
                        yield ref

        for path, schema in iter_registered_schemas():
            resolver = config_schema.RefResolver.from_schema(schema)
            for ref in refs_in(schema):
                try:
                    with resolver.resolving(ref):
                        pass
                except jsonschema.RefResolutionError:
                    assert False, '$ref %s in schema %s is invalid' % (ref, path)

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

    def test_custom_error(self):
        schema = {'type': 'string', 'error': 'This is not okay'}
        v = config_schema.SchemaValidator(schema)
        errors = list(v.iter_errors(13))
        assert errors[0].message == schema['error']

    def test_custom_error_template(self):
        schema = {'type': 'string', 'minLength': 10, 'error': '{{validator}} failed for {{instance}}'}
        v = config_schema.SchemaValidator(schema)
        errors = list(v.iter_errors(13))
        assert errors[0].message == "type failed for 13"
        errors = list(v.iter_errors('aoeu'))
        assert errors[0].message == "minLength failed for aoeu"

    def test_builtin_error_rewriting(self):
        schema = {'type': 'object'}
        v = config_schema.SchemaValidator(schema)
        with mock.patch.object(config_schema.ValidationError, 'message_type') as message_type:
            message_type.return_value = 'I am error'
            errors = list(v.iter_errors(42))
            assert errors[0].message == 'I am error'
