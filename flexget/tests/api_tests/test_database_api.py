from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json

from flexget.api.app import base_message
from flexget.api.core.database import ObjectsContainer as OC


class TestDatabaseAPI(object):
    config = 'tasks: {}'

    def test_database_methods(self, api_client, schema_match):
        rsp = api_client.json_post('/database/cleanup/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.json_post('/database/vacuum/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.json_post('/database/reset_plugin/?plugin_name=bla', data=json.dumps({}))
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.json_post('/database/reset_plugin/?plugin_name=tvmaze', data=json.dumps({}))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/database/plugins/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_list, data)
        assert not errors
