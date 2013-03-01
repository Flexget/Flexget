from __future__ import unicode_literals, division, absolute_import

import jsonschema

from flexget import config_schema
from flexget import plugin
from tests import FlexGetBase


class TestSchemaValidator(FlexGetBase):
    def test_plugin_schemas_are_valid(self):
        for p in plugin.plugins.values():
            if p.schema is None:
                continue
            try:
                config_schema.SchemaValidator.check_schema(p.schema)
            except jsonschema.SchemaError as e:
                assert False, 'plugin `%s` has an invalid schema. %s %s' % (
                    p.name, '/'.join(str(p) for p in e.path), e.message)

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
