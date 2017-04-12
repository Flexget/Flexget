from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from flexget.api.plugins.movie_list import ObjectsContainer as OC
from flexget.utils import json


class TestETAG(object):
    config = 'tasks: {}'

    def test_etag(self, api_client, schema_match):
        # Test ETag creation and usage

        # Create movie lists
        list_1 = {'name': 'list_1'}
        list_2 = {'name': 'list_2'}

        # Create lists
        rsp = api_client.json_post('/movie_list/', data=json.dumps(list_1))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        rsp = api_client.json_post('/movie_list/', data=json.dumps(list_2))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get ETag
        rsp = api_client.get('/movie_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        etag = rsp.headers.get('etag')
        assert etag is not None

        # Test If-None-Match
        header = {'If-None-Match': etag}
        rsp = api_client.head('/movie_list/', headers=header)
        assert rsp.status_code == 304, 'Response code is %s' % rsp.status_code

        header = {'If-None-Match': etag}
        rsp = api_client.get('/movie_list/', headers=header)
        assert rsp.status_code == 304, 'Response code is %s' % rsp.status_code
        data = rsp.get_data(as_text=True)
        assert data is ''

        header = {'If-None-Match': '*'}
        rsp = api_client.head('/movie_list/', headers=header)
        assert rsp.status_code == 304, 'Response code is %s' % rsp.status_code

        # Test If-Match
        header = {'If-Match': 'not_etag'}
        rsp = api_client.head('/movie_list/', headers=header)
        assert rsp.status_code == 412, 'Response code is %s' % rsp.status_code

        # Change data
        list_3 = {'name': 'list_3'}
        rsp = api_client.json_post('/movie_list/', data=json.dumps(list_3))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        header = {'If-None-Match': etag}
        rsp = api_client.get('/movie_list/', headers=header)
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_lists, data)
        assert not errors

        # Verify all 3 lists are received as payload
        assert len(data) == 3
