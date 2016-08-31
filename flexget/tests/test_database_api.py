from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin


class TestDatabaseAPI(object):
    config = 'tasks: {}'

    def test_database_methods(self, api_client):
        rsp = api_client.get('/database/cleanup/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/database/vacuum/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/database/reset_plugin/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/database/reset_plugin/?plugin_name=bla')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/database/reset_plugin/?plugin_name=tvmaze')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/database/plugins/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
