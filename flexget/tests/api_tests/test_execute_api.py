from __future__ import unicode_literals, division, absolute_import

import json

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from flexget.api.app import base_message
from flexget.api.core.tasks import ObjectsContainer as OC


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

    def test_execute(self, api_client, manager, schema_match):
        # Minimal payload
        payload = {'tasks': ['test_task']}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.accepted) == 1

    def test_inject_plain(self, api_client, manager, schema_match):
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
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 0

    def test_inject_accept(self, api_client, manager, schema_match):
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

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

    def test_inject_force(self, api_client, manager, schema_match):
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
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        # Rejected due to Seen
        assert len(task.accepted) == 0

        # Forcing the entry not to be disabled
        entry['force'] = True

        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

    def test_inject_with_fields(self, api_client, manager, schema_match):
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
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1

        entry = task.find_entry(title='injected')
        assert entry['imdb_id'] == "tt1234567"
        assert entry['tmdb_id'] == "1234567"

    def test_multiple_entries(self, api_client, manager, schema_match):
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
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 2
        assert len(task.accepted) == 2

    def test_2nd_endpoint(self, api_client, manager, schema_match):
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
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

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

    def test_execute_multiple_tasks(self, api_client, manager, schema_match):
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps({}))
        assert rsp.status_code == 422
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload = {'tasks': ['non_existing_test_task']}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload = {'tasks': ['test_task1', 'test_task2']}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors
