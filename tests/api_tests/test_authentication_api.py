import base64
import json

import pytest

from flexget.api.app import base_message
from flexget.webserver import change_password


class TestAuthenticationAPI:
    config = "{'tasks': {}}"

    def test_login(self, api_client, schema_match):
        rsp = api_client.json_post('/auth/login/', data=json.dumps({}))
        assert rsp.status_code == 422, f'Response code is {rsp.status_code}'

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        invalid_credentials = {'username': 'bla', 'password': 'bla'}

        rsp = api_client.json_post('/auth/login/', data=json.dumps(invalid_credentials))
        assert rsp.status_code == 401, f'Response code is {rsp.status_code}'

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    @pytest.mark.parametrize('password', ['AVer123y$ron__g', 'AVer123y:$ron__:g:'])
    def test_basic_auth(self, api_client, password):
        change_password(username='flexget', password=password)

        def status(pwd):
            auth = base64.b64encode(f'flexget:{pwd}'.encode()).decode()
            # A new client for each request, so no session cookie is reused
            client = api_client.client.application.test_client()
            headers = {'Authorization': f'Basic {auth}'}
            return client.get('/tasks/', headers=headers).status_code

        assert status(password) == 200
        assert status(password[:-1]) == 401
        assert status(password.split(':')[0] + 'x') == 401
