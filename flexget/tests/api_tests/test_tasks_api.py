from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json

from mock import patch

from flexget.api.app import base_message
from flexget.api.core.tasks import ObjectsContainer as OC
from flexget.manager import Manager


class TestTaskAPI(object):
    config = """
        tasks:
          test:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
        """

    def test_list_tasks(self, api_client, schema_match):
        rsp = api_client.get('/tasks/')
        data = json.loads(rsp.get_data(as_text=True))

        # TODO Need to figure out how to do this
        # errors = schema_match(OC.tasks_list_object, data)
        # assert not errors
        assert data == [
            {
                'name': 'test',
                'config': {
                    'mock': [{'title': 'entry 1'}],
                    'rss': {
                        'url': u'http://test/rss',
                        'group_links': False,
                        'ascii': False,
                        'escape': False,
                        'silent': False,
                        'all_entries': True
                    }
                },
            }
        ]

    @patch.object(Manager, 'save_config')
    def test_add_task(self, mocked_save_config, api_client, manager, schema_match):
        new_task = {
            'name': 'new_task',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://test/rss'}
            }
        }

        return_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {
                    'url': u'http://test/rss',
                    'group_links': False,
                    'ascii': False,
                    'escape': False,
                    'silent': False,
                    'all_entries': True
                }
            },
        }

        rsp = api_client.json_post('/tasks/', data=json.dumps(new_task))
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_return_object, data)
        assert not errors

        assert rsp.status_code == 201
        assert mocked_save_config.called
        assert data == new_task
        assert manager.user_config['tasks']['new_task'] == new_task['config']
        assert manager.config['tasks']['new_task'] == return_task['config']

    def test_add_task_existing(self, api_client, schema_match):
        new_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}]
            }
        }

        rsp = api_client.json_post('/tasks/', data=json.dumps(new_task))
        assert rsp.status_code == 409
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_get_task(self, api_client, schema_match):
        rsp = api_client.get('/tasks/test/')
        assert rsp.status_code == 200

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.task_return_object, data)
        assert not errors

        assert data == {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {
                    'url': u'http://test/rss',
                    'group_links': False,
                    'ascii': False,
                    'escape': False,
                    'silent': False,
                    'all_entries': True
                }
            },
        }

        # Non existent task
        rsp = api_client.get('/tasks/bla/')
        data = json.loads(rsp.get_data(as_text=True))
        assert rsp.status_code == 404

        errors = schema_match(base_message, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_update_task(self, mocked_save_config, api_client, manager, schema_match):
        same_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        rsp = api_client.json_put('/tasks/test/', data=json.dumps(same_task))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.task_return_object, data)
        assert not errors

        updated_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        rsp = api_client.json_put('/tasks/test/', data=json.dumps(updated_task))

        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.task_return_object, data)
        assert not errors
        assert mocked_save_config.called
        assert data == updated_task
        assert manager.user_config['tasks']['test'] == updated_task['config']
        assert manager.config['tasks']['test'] == updated_task['config']

        # Non existent task
        rsp = api_client.json_put('/tasks/bla/', data=json.dumps(updated_task))
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_rename_task(self, mocked_save_config, api_client, manager, schema_match):
        updated_task = {
            'name': 'new_test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        rsp = api_client.json_put('/tasks/test/', data=json.dumps(updated_task))

        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.task_return_object, data)
        assert not errors
        assert mocked_save_config.called
        assert data == updated_task
        assert 'test' not in manager.user_config['tasks']
        assert 'test' not in manager.config['tasks']
        assert manager.user_config['tasks']['new_test'] == updated_task['config']
        assert manager.config['tasks']['new_test'] == updated_task['config']

    @patch.object(Manager, 'save_config')
    def test_delete_task(self, mocked_save_config, api_client, manager, schema_match):
        rsp = api_client.delete('/tasks/test/')

        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors
        assert mocked_save_config.called
        assert 'test' not in manager.user_config['tasks']
        assert 'test' not in manager.config['tasks']

        # Non existent task
        rsp = api_client.delete('/tasks/bla/')

        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors


class TestTaskQueue(object):
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

    def test_task_queue(self, api_client, schema_match, manager):
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
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        # Get task queue
        rsp = api_client.get('/tasks/queue/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_queue_schema, data)
        assert not errors

        assert len(data) == 1

        # Execute tasj
        task = manager.task_queue.run_queue.get(timeout=0.5)
        assert task

        # Check queue again
        rsp = api_client.get('/tasks/queue/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_queue_schema, data)
        assert not errors

        assert data == []


class TestDisabledTasks(object):
    config = """
        tasks:
          live_task:
            mock:
            - title: foo
          _disabled_task:
            mock:
            - title: bar
    """

    def test_only_active_tasks_return(self, api_client):
        rsp = api_client.get('/tasks/')
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 1
        assert not data[0].get('name') == '_disabled_task'
