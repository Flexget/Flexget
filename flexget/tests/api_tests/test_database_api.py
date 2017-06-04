from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json

import pytest

from flexget.api.app import base_message
from flexget.api.core.database import ObjectsContainer as OC


class TestDatabaseAPI(object):
    config = 'tasks: {}'

    @pytest.mark.parametrize('operation, plugin_name, status, schema', [
        ('cleanup', None, 200, base_message),
        ('vacuum', None, 200, base_message),
        ('plugin_reset', 'bla', 400, base_message),
        ('plugin_reset', 'tvmaze', 200, base_message),
        ('list_plugins', None, 200, OC.plugin_list),
    ])
    def test_database_methods(self, operation, plugin_name, status, schema, api_client, schema_match):
        payload = {'operation': operation}
        if plugin_name:
            payload['plugin_name'] = plugin_name

        rsp = api_client.json_post('/database/', data=json.dumps(payload))
        assert rsp.status_code == status, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(schema, data)
        assert not errors
