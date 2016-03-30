import json
import os

from mock import patch

from flexget import __version__
from flexget.api import __version__ as __api_version__
from flexget.manager import Manager, Session
from flexget.plugins.filter.seen import SeenEntry
from tests.conftest import MockManager


class TestValidator(object):
    config = '{tasks: {}}'

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


class TestExecuteAPI(object):
    config = """
        tasks:
          test_task:
            mock:
              - title: accept_me
              - title: reject_me
            accept_all: yes
        """

    def test_execute(self, api_client):
        # No parameters
        rsp = api_client.json_post('/tasks/test_task/execute/', data=json.dumps({'log': True}))
        assert rsp.status_code == 200

        with Session() as session:
            query = session.query(SeenEntry).all()
            assert len(query) == 1

# TODO: Finish tests
