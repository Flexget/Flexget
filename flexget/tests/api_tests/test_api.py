from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import json
import os
import pytest
from flexget.utils.tools import get_latest_flexget_version_number

from mock import patch

from flexget import __version__
from flexget.api import __version__ as __api_version__
from flexget.manager import Manager
from flexget.tests.conftest import MockManager


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
        assert json.loads(rsp.get_data(as_text=True)) == {'pid': os.getpid()}

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
        assert json.loads(rsp.get_data(as_text=True)) == {
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

    @pytest.mark.online
    def test_version(self, api_client):
        latest = get_latest_flexget_version_number()

        rsp = api_client.get('/server/version/')
        assert rsp.status_code == 200
        assert json.loads(rsp.get_data(as_text=True)) == {'flexget_version': __version__,
                                                          'api_version': __api_version__,
                                                          'latest_version': latest}


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
        data = json.loads(rsp.get_data(as_text=True))
        assert data == [
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
        assert json.loads(rsp.get_data(as_text=True)) == new_task
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
        data = json.loads(rsp.get_data(as_text=True))
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
        assert json.loads(rsp.get_data(as_text=True)) == updated_task
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
        assert json.loads(rsp.get_data(as_text=True)) == updated_task
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
    @staticmethod
    def get_task_queue(manager):
        """ Used to execute task queue"""
        assert len(manager.task_queue) == 1
        task = manager.task_queue.run_queue.get(timeout=0.5)
        assert task
        return task

    config = """
        tasks:
          test_task:
            mock:
              - title: accept_me
              - title: reject_me
            regexp:
              accept:
                - accept
              reject:
                - reject
        """

    def test_execute(self, api_client, manager):
        # Minimal payload
        payload = {'tasks': ['test_task']}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.accepted) == 1

    def test_inject_plain(self, api_client, manager):
        entry = {
            'title': "injected",
            'url': 'http://test.com'
        }

        payload = {
            "inject": [entry],
            'tasks': ['test_task']
        }
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 0

    def test_inject_accept(self, api_client, manager):
        entry = {
            'title': "injected",
            'url': 'http://test.com',
            'accept': True,
            'tasks': ['test_task']
        }

        payload = {
            "inject": [entry],
            'tasks': ['test_task']
        }
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

    def test_inject_force(self, api_client, manager):
        entry = {
            'title': "accept",
            'url': 'http://test.com',
        }

        payload = {
            "inject": [entry],
            'tasks': ['test_task']
        }
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        # Rejected due to Seen
        assert len(task.accepted) == 0

        # Forcing the entry not to be disabled
        entry['force'] = True

        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

    def test_inject_with_fields(self, api_client, manager):
        fields = {'imdb_id': "tt1234567",
                  'tmdb_id': "1234567"}
        entry = {
            'title': "injected",
            'url': 'http://test.com',
            'fields': fields,
            'accept': True
        }

        payload = {
            "inject": [entry],
            'tasks': ['test_task']
        }

        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

        entry = task.find_entry(title='injected')
        assert entry['imdb_id'] == "tt1234567"
        assert entry['tmdb_id'] == "1234567"

    def test_multiple_entries(self, api_client, manager):
        entry1 = {
            'title': "entry1",
            'url': 'http://test.com',
            'accept': True
        }
        entry2 = {
            'title': "entry2",
            'url': 'http://test.com',
            'accept': True
        }

        payload = {
            "inject": [entry1, entry2],
            'tasks': ['test_task']
        }
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 2
        assert len(task.accepted) == 2

    def test_2nd_endpoint(self, api_client, manager):
        entry = {
            'title': "injected",
            'url': 'http://test.com',
            'accept': True
        }

        payload = {
            "inject": [entry],
            'tasks': ['test_task']
        }
        rsp = api_client.json_post('/inject/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1


class TestExecuteMultipleTasks(object):
    config = """
        tasks:
          test_task1:
            mock:
              - title: accept_me1
            accept_all: yes
          test_task2:
            mock:
              - title: accept_me2
            accept_all: yes
        """

    def test_execute_multiple_tasks(self, api_client, manager):
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps({}))
        assert rsp.status_code == 422

        payload = {'tasks': ['non_existing_test_task']}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 404

        payload = {'tasks': ['test_task1', 'test_task2']}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200
