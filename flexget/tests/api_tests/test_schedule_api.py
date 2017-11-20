from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.api.app import base_message
from flexget.api.plugins.schedule import ObjectsContainer as OC
from flexget.manager import Manager
from flexget.utils import json
from mock import patch


class TestEmptyScheduledAPI(object):
    config = 'tasks: {}'

    def test_empty_schedules_get(self, api_client, schema_match):
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        assert data == []

    @patch.object(Manager, 'save_config')
    def test_schedules_post(self, mocked_save_config, api_client, schema_match):
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }

        rsp = api_client.json_post('/schedules/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors
        assert mocked_save_config.called

        del data['id']
        assert data == payload


class TestScheduledAPI(object):
    schedule = {'tasks': ['test1'],
                'interval': {'minutes': 15}}

    config = """
            schedules:
              - tasks:
                  - test1
                interval:
                  minutes: 15
            tasks:
              test1:
                rss:
                  url: http://test/rss
                mock:
                  - title: entry 1
            """

    def test_schedules_get(self, api_client, schema_match):
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        for key, value in self.schedule.items():
            assert data[0][key] == value

    @patch.object(Manager, 'save_config')
    def test_schedules_post(self, mocked_save_config, api_client, schema_match):
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }

        rsp = api_client.json_post('/schedules/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors
        assert mocked_save_config.called

        del data['id']
        assert data == payload

    def test_schedules_id_get(self, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        schedule_id = data[0]['id']

        # Real schedule ID
        rsp = api_client.get('/schedules/{}/'.format(schedule_id))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors

        for key, value in self.schedule.items():
            assert data[key] == value

        # Non-existent schedule ID
        rsp = api_client.get('/schedules/12312/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_schedules_id_put(self, mocked_save_config, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        schedule_id = data[0]['id']
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }
        rsp = api_client.json_put('/schedules/{}/'.format(schedule_id), data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors
        assert mocked_save_config.called

        del data['id']
        assert data == payload

        rsp = api_client.json_put('/schedules/1011/', data=json.dumps(payload))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_schedules_id_delete(self, mocked_save_config, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        schedule_id = data[0]['id']

        rsp = api_client.delete('/schedules/{}/'.format(schedule_id))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
        assert mocked_save_config.called

        rsp = api_client.delete('/schedules/111/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
        assert mocked_save_config.called


class TestPositiveBooleanSchedule(object):
    config = """
        schedules: yes
        tasks:
          test1:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
    """

    def test_schedules_get(self, api_client, schema_match):
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_schedules_post(self, mocked_save_config, api_client, schema_match):
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }

        rsp = api_client.json_post('/schedules/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors
        assert mocked_save_config.called

        del data['id']
        assert data == payload

    def test_schedules_id_get(self, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        schedule_id = data[0]['id']

        # Real schedule ID
        rsp = api_client.get('/schedules/{}/'.format(schedule_id))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors

        # Non-existent schedule ID
        rsp = api_client.get('/schedules/12312/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_schedules_id_put(self, mocked_save_config, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        schedule_id = data[0]['id']
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }
        rsp = api_client.json_put('/schedules/{}/'.format(schedule_id), data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors
        assert mocked_save_config.called

        del data['id']
        assert data == payload

        rsp = api_client.json_put('/schedules/1011/', data=json.dumps(payload))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_schedules_id_delete(self, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

        schedule_id = data[0]['id']

        rsp = api_client.delete('/schedules/{}/'.format(schedule_id))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestNegativeBooleanSchedule(object):
    config = """
        schedules: no
        tasks:
          test1:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
    """

    def test_schedules_get(self, api_client, schema_match):
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_schedules_post(self, api_client, schema_match):
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }

        rsp = api_client.json_post('/schedules/', data=json.dumps(payload))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_schedules_id_get(self, api_client, schema_match):
        rsp = api_client.get('/schedules/1/')
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_schedules_id_put(self, api_client, schema_match):
        payload = {
            'tasks': ['test2', 'test3'],
            'interval': {'minutes': 10}
        }
        rsp = api_client.json_put('/schedules/1/', data=json.dumps(payload))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_schedules_id_delete(self, api_client, schema_match):
        # Get schedules to get their IDs
        rsp = api_client.delete('/schedules/1/')
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
