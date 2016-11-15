from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
import requests


@pytest.mark.online
class TestCachedAPI(object):
    config = 'tasks: {}'

    def test_cached_api(self, api_client):
        rsp = api_client.get('/cached/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/cached/?url=bla')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        image_url = 'http://thetvdb.com/banners/fanart/original/281662-18.jpg'
        response = requests.get(image_url)

        assert response.status_code == 200

        rsp = api_client.get('/cached/?url={}'.format(image_url))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert rsp.data == response.content

        rsp = api_client.get('/cached/?url={}?force=true'.format(image_url))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
