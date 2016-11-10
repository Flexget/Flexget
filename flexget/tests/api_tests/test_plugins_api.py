from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.api.app import base_message
from flexget.api.core.plugins import ObjectsContainer as OC
from flexget.utils import json


class TestPluginsAPI(object):
    config = 'tasks: {}'

    def test_plugins_api(self, api_client, schema_match):
        rsp = api_client.get('/plugins/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_list_reply, data)
        assert not errors

        rsp = api_client.get('/plugins/?include_schema=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_list_reply, data)
        assert not errors

        rsp = api_client.get('/plugins/?group=search')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_list_reply, data)
        assert not errors

        rsp = api_client.get('/plugins/?group=fgfg')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_list_reply, data)
        assert not errors
        assert data == []

        rsp = api_client.get('/plugins/?phase=fgfg')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/plugins/?phase=input')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_list_reply, data)
        assert not errors

        rsp = api_client.get('/plugins/bla/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/plugins/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_object, data)
        assert not errors

        rsp = api_client.get('/plugins/seen/?include_schema=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.plugin_object, data)
        assert not errors
