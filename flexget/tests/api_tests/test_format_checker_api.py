from flexget.api.app import base_message
from flexget.utils import json


class TestFormatChecker:
    config = 'tasks: {}'

    def test_quality(self, api_client, schema_match):
        payload1 = {'quality': '720p'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'quality': '720p-1080p'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_quality_req(self, api_client, schema_match):
        payload1 = {'quality_requirements': '720p-1080p'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'quality': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_time(self, api_client, schema_match):
        payload = {'time': '10:00'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload = {'time': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_interval(self, api_client, schema_match):
        payload1 = {'interval': '1 day'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'interval': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_percent(self, api_client, schema_match):
        payload1 = {'percent': '79%'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'percent': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_size(self, api_client, schema_match):
        payload1 = {'size': '4GB'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'percent': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_regex(self, api_client, schema_match):
        payload1 = {'regex': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'regex': '(('}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_file(self, api_client, schema_match):
        payload1 = {'file': 'test_format_checker_api.py'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'file': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_path(self, api_client, schema_match):
        payload1 = {'path': '../api_tests'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'path': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_url(self, api_client, schema_match):
        payload1 = {'url': 'http://google.com'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'url': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_episode_identifier(self, api_client, schema_match):
        payload1 = {'episode_identifier': 's01e01'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'episode_identifier': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_episode_or_season_id(self, api_client, schema_match):
        payload1 = {'episode_or_season_id': 's01'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'episode_or_season_id': 'bla'}

        rsp = api_client.json_post('/format_check/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
