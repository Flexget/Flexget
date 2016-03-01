import json
import os
import pytest
from mock import patch
from flexget import __version__
from flexget.api import app, __version__ as __api_version__
from flexget.manager import Manager
from flexget.webserver import User
from flexget.manager import Session
from tests.conftest import MockManager


class APIClient(object):
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = app.test_client()

    def _append_header(self, key, value, kwargs):
        if 'headers' not in kwargs:
            kwargs['headers'] = {}

        kwargs['headers'][key] = value

    def json_post(self, *args, **kwargs):
        self._append_header('Content-Type', 'application/json', kwargs)
        if kwargs.get('auth', True):
            self._append_header('Authorization', 'Token %s' % self.api_key, kwargs)
        return self.client.post(*args, **kwargs)

    def json_put(self, *args, **kwargs):
        self._append_header('Content-Type', 'application/json', kwargs)
        if kwargs.get('auth', True):
            self._append_header('Authorization', 'Token %s' % self.api_key, kwargs)
        return self.client.put(*args, **kwargs)

    def get(self, *args, **kwargs):
        if kwargs.get('auth', True):
            self._append_header('Authorization', 'Token %s' % self.api_key, kwargs)

        return self.client.get(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if kwargs.get('auth', True):
            self._append_header('Authorization', 'Token %s' % self.api_key, kwargs)

        return self.client.delete(*args, **kwargs)


@pytest.fixture()
def api_client(manager):
    with Session() as session:
        user = session.query(User).first()
        if not user:
            user = User(name='flexget', password='flexget')
            session.add(user)
            session.commit()
        return APIClient(user.token)


class TestValidator(object):
    def test_invalid_payload(self, api_client):
        new_task = {
            'name': 'new_task',
            'config': {
                'invalid_plugin': [{'title': 'entry 1'}],
                'fake_plugin2': {'url': 'http://test/rss'}
            }
        }

        rsp = api_client.json_post('/tasks/', data=json.dumps(new_task))

        assert rsp.status_code == 400
        data = json.loads(rsp.data)
        assert data.get('code') == 400
        assert data.get('message') == 'validation error'
        assert data.get('validation_errors')
        assert 'The keys' in data['validation_errors'][0]['message']
        assert 'invalid_plugin' in data['validation_errors'][0]['message']
        assert 'fake_plugin2' in data['validation_errors'][0]['message']


class TestServerAPI(object):
    config = """
        tasks:
          test:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
        """

    def test_pid(self, api_client):
        rsp = api_client.get('/server/pid/', headers={})
        assert rsp.status_code == 200
        assert json.loads(rsp.data) == {'pid': os.getpid()}

    @patch.object(MockManager, 'load_config')
    def test_reload(self, mocked_load_config, api_client):
        rsp = api_client.get('/server/reload/')
        assert rsp.status_code == 200
        assert mocked_load_config.called

    @patch.object(Manager, 'shutdown')
    def test_shutdown(self, mocked_shutdown, api_client):
        api_client.get('/server/shutdown/')
        assert mocked_shutdown.called

    def test_get_config(self, api_client):
        rsp = api_client.get('/server/config/')
        assert rsp.status_code == 200
        assert json.loads(rsp.data) == {
            'tasks': {
                'test': {
                    'mock': [{'title': 'entry 1'}],
                    'rss': {
                        'url': u'http://test/rss',
                        'group_links': False,
                        'ascii': False,
                        'silent': False,
                        'all_entries': True
                    }
                }
            }
        }

    def test_version(self, api_client):
        rsp = api_client.get('/server/version/')
        assert rsp.status_code == 200
        assert json.loads(rsp.data) == {'flexget_version': __version__, 'api_version': __api_version__}


class TestTaskAPI(object):
    config = """
        tasks:
          test:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
        """

    def test_list_tasks(self, api_client):
        rsp = api_client.get('/tasks/')
        data = json.loads(rsp.data)
        assert data == {
            'tasks': [
                {
                    'name': 'test',
                    'config': {
                        'mock': [{'title': 'entry 1'}],
                        'rss': {
                            'url': u'http://test/rss',
                            'group_links': False,
                            'ascii': False,
                            'silent': False,
                            'all_entries': True
                        }
                    },
                }
            ]
        }

    @patch.object(Manager, 'save_config')
    def test_add_task(self, mocked_save_config, api_client, manager):
        new_task = {
            'name': 'new_task',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://test/rss'}
            }
        }

        rsp = api_client.json_post('/tasks/', data=json.dumps(new_task))

        assert rsp.status_code == 201
        assert mocked_save_config.called
        assert json.loads(rsp.data) == new_task
        assert manager.user_config['tasks']['new_task'] == new_task['config']
        assert manager.config['tasks']['new_task'] == new_task['config']

    def test_add_task_existing(self, api_client):
        new_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}]
            }
        }

        rsp = api_client.json_post('/tasks/', data=json.dumps(new_task))
        assert rsp.status_code == 409

    def test_get_task(self, api_client):
        rsp = api_client.get('/tasks/test/')
        data = json.loads(rsp.data)
        assert data == {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {
                    'url': u'http://test/rss',
                    'group_links': False,
                    'ascii': False,
                    'silent': False,
                    'all_entries': True
                }
            },
        }

    @patch.object(Manager, 'save_config')
    def test_update_task(self, mocked_save_config, api_client, manager):
        updated_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        rsp = api_client.json_put('/tasks/test/', data=json.dumps(updated_task))

        assert rsp.status_code == 200
        assert mocked_save_config.called
        assert json.loads(rsp.data) == updated_task
        assert manager.user_config['tasks']['test'] == updated_task['config']
        assert manager.config['tasks']['test'] == updated_task['config']

    @patch.object(Manager, 'save_config')
    def test_rename_task(self, mocked_save_config, api_client, manager):
        updated_task = {
            'name': 'new_test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        rsp = api_client.json_put('/tasks/test/', data=json.dumps(updated_task))

        assert rsp.status_code == 201
        assert mocked_save_config.called
        assert json.loads(rsp.data) == updated_task
        assert 'test' not in manager.user_config['tasks']
        assert 'test' not in manager.config['tasks']
        assert manager.user_config['tasks']['new_test'] == updated_task['config']
        assert manager.config['tasks']['new_test'] == updated_task['config']

    @patch.object(Manager, 'save_config')
    def test_delete_task(self, mocked_save_config, api_client, manager):
        rsp = api_client.delete('/tasks/test/')

        assert rsp.status_code == 200
        assert mocked_save_config.called
        assert 'test' not in manager.user_config['tasks']
        assert 'test' not in manager.config['tasks']

# TODO: Finish tests
