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
            except Exception as e:
                assert False, 'plugin `%s` has an invalid schema. %s' % (path, e)

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
        # accept_all schema should be for type boolean
        assert not config_schema.process_config(True, schema)
        assert config_schema.process_config(14, schema)

    def test_custom_format_checker(self):
        schema = {'type': 'string', 'format': 'quality'}
        assert not config_schema.process_config('720p', schema)
        assert config_schema.process_config('aoeu', schema)

    def test_custom_error(self):
        schema = {'type': 'string', 'error': 'This is not okay'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == schema['error']

    def test_custom_error_template(self):
        schema = {'type': 'string', 'minLength': 10, 'error': '{{validator}} failed for {{instance}}'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == "type failed for 13"
        errors = config_schema.process_config('aoeu', schema)
        assert errors[0].message == "minLength failed for aoeu"

    def test_custom_keyword_error(self):
        schema = {'type': 'string', 'error_type': 'This is not okay'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == schema['error_type']

    def test_custom_keyword_error_overrides(self):
        schema = {'type': 'string', 'error_type': 'This is not okay', 'error': 'This is worse'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == schema['error_type']

    def test_error_with_path(self):
        schema = {'properties': {'p': {'items': {'type': 'string', 'error': 'ERROR'}}}}
        errors = config_schema.process_config({'p': [13]}, schema)
        assert errors[0].json_pointer == '/p/0'
        assert errors[0].message == 'ERROR'

    def test_builtin_error_rewriting(self):
        schema = {'type': 'object'}
        errors = config_schema.process_config(42, schema)
        # We don't call them objects around here
        assert 'object' not in errors[0].message
        assert 'dict' in errors[0].message

    def test_anyOf_branch_is_chosen_based_on_type_errors(self):
        schema = {
            "anyOf": [
                {"type": ["string", "array"]},
                {
                    "anyOf": [
                        {"type": "integer"},
                        {"type": "number", "minimum": 5}
                    ]
                }
            ]
        }
        # If there are type errors on both sides, it should be a virtual type error with all types
        errors = config_schema.process_config(True, schema)
        assert len(errors) == 1
        assert tuple(errors[0].schema_path) == ('anyOf', 'type')
        # It should have all the types together
        assert set(errors[0].validator_value) == set(['string', 'array', 'number', 'integer'])
        # If there are no type errors going down one branch it should choose it
        errors = config_schema.process_config(1.5, schema)
        assert len(errors) == 1
        assert errors[0].validator == 'minimum'

    def test_oneOf_branch_is_chosen_based_on_type_errors(self):
        schema = {
            "oneOf": [
                {"type": ["string", "array"]},
                {
                    "oneOf": [
                        {"type": "integer"},
                        {"type": "number", "minimum": 5}
                    ]
                }
            ]
        }
        errors = config_schema.process_config(True, schema)
        # If there are type errors on both sides, it should be a virtual type error with all types
        assert len(errors) == 1
        assert tuple(errors[0].schema_path) == ('oneOf', 'type')
        # It should have all the types together
        assert set(errors[0].validator_value) == set(['string', 'array', 'number', 'integer'])
        # If there are no type errors going down one branch it should choose it
        errors = config_schema.process_config(1.5, schema)
        assert len(errors) == 1
        assert errors[0].validator == 'minimum'

    def test_defaults_are_filled(self):
        schema = {"properties": {"p": {"default": 5}}}
        config = {}
        config_schema.process_config(config, schema)
        assert config["p"] == 5

    def test_defaults_does_not_override_explicit_value(self):
        schema = {"properties": {"p": {"default": 5}}}
        config = {"p": "foo"}
        config_schema.process_config(config, schema)
        assert config["p"] == "foo"
