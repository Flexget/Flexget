from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.utils import json


class TestPluginsAPI(object):
    config = 'tasks: {}'

    def test_plugins_api(self, api_client):
        rsp = api_client.get('/plugins/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/plugins/?include_schema=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/plugins/?group=search')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/plugins/?group=fgfg')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True))['plugin_list'] == []

        rsp = api_client.get('/plugins/?phase=fgfg')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/plugins/?phase=input')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/plugins/bla/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/plugins/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
