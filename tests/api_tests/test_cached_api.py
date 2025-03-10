import pytest
import requests


@pytest.mark.online
class TestCachedAPI:
    config = 'tasks: {}'

    def test_cached_api(self, api_client):
        rsp = api_client.get('/cached/')
        assert rsp.status_code == 400, f'Response code is {rsp.status_code}'

        rsp = api_client.get('/cached/?url=bla')
        assert rsp.status_code == 400, f'Response code is {rsp.status_code}'

        image_url = 'http://thetvdb.com/banners/fanart/original/281662-18.jpg'
        response = requests.get(image_url)

        assert response.status_code == 200

        rsp = api_client.get(f'/cached/?url={image_url}')
        assert rsp.status_code == 200, f'Response code is {rsp.status_code}'

        assert rsp.data == response.content

        rsp = api_client.get(f'/cached/?url={image_url}?force=true')
        assert rsp.status_code == 200, f'Response code is {rsp.status_code}'
