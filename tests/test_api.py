from flexget import api
from tests import FlexGetBase
import json

from flexget.manager import Manager

from mock import patch

def test_schema_models():
    # TODO: Loop through registered schema models, validate against metaschema
    pass


class APITest(FlexGetBase):

    def __init__(self):
        self.client = api.app.test_client()
        FlexGetBase.__init__(self)

    def json_post(self, *args, **kwargs):
        if 'header' not in kwargs:
            kwargs['headers'] = [('Content-Type', 'application/json')]
        return self.client.post(*args, **kwargs)


class TestServerAPI(APITest):

    def test_pid(self):
        pass

    def test_reload(self):
        pass

    def test_shutdown(self):
        pass

    def test_get_config(self):
        pass

    def test_version(self):
        pass

    def test_log(self):
        pass


class TestTaskAPI(APITest):

    __yaml__ = """
        tasks:
          test:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
        """

    def test_list_tasks(self):
        req = self.client.get('/tasks/')
        data = json.loads(req.data)
        assert data == {
            'tasks': [
                {
                    'name': 'test',
                    'config': {
                        'mock': [{'title': 'entry 1'}],
                        'rss': {'url': 'http://test/rss'}
                    },
                }
            ]
        }

    @patch.object(Manager, 'save_config')
    def test_add_task(self, mocked_save_config):
        new_task = {
            'name': 'new_task',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://test/rss'}
            }
        }

        req = self.json_post('/tasks/', data=json.dumps(new_task))

        assert req.status_code == 201
        assert mocked_save_config.called
        assert json.loads(req.data) == new_task
        assert self.manager.user_config['tasks']['new_task'] == new_task['config']

        # With defaults
        new_task['config']['rss']['ascii'] = False
        new_task['config']['rss']['group_links'] = False
        new_task['config']['rss']['silent'] = False
        new_task['config']['rss']['all_entries'] = True
        assert self.manager.config['tasks']['new_task'] == new_task['config']

    def test_add_task_existing(self):
        new_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}]
            }
        }

        req = self.json_post('/tasks/', data=json.dumps(new_task))
        assert req.status_code == 409

    def test_get_task(self):
        req = self.client.get('/tasks/test/')
        data = json.loads(req.data)
        assert data == {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://test/rss'}
            },
        }

    @patch.object(Manager, 'save_config')
    def test_update_task(self, mocked_save_config):
        updated_task = {
            'name': 'test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        req = self.json_post('/tasks/test/', data=json.dumps(updated_task))

        assert req.status_code == 200
        assert mocked_save_config.called
        assert json.loads(req.data) == updated_task
        assert self.manager.user_config['tasks']['test'] == updated_task['config']

        # With defaults
        updated_task['config']['rss']['ascii'] = False
        updated_task['config']['rss']['group_links'] = False
        updated_task['config']['rss']['silent'] = False
        updated_task['config']['rss']['all_entries'] = True
        assert self.manager.config['tasks']['test'] == updated_task['config']

    @patch.object(Manager, 'save_config')
    def test_rename_task(self, mocked_save_config):
        updated_task = {
            'name': 'new_test',
            'config': {
                'mock': [{'title': 'entry 1'}],
                'rss': {'url': 'http://newurl/rss'}
            }
        }

        req = self.json_post('/tasks/test/', data=json.dumps(updated_task))

        assert req.status_code == 201
        assert mocked_save_config.called
        assert json.loads(req.data) == updated_task
        assert 'test' not in self.manager.user_config['tasks']
        assert 'test' not in self.manager.config['tasks']
        assert self.manager.user_config['tasks']['new_test'] == updated_task['config']

        # With defaults
        updated_task['config']['rss']['ascii'] = False
        updated_task['config']['rss']['group_links'] = False
        updated_task['config']['rss']['silent'] = False
        updated_task['config']['rss']['all_entries'] = True
        assert self.manager.config['tasks']['new_test'] == updated_task['config']

    @patch.object(Manager, 'save_config')
    def test_delete_task(self, mocked_save_config):
        req = self.client.delete('/tasks/test/')

        assert req.status_code == 200
        assert mocked_save_config.called
        assert 'test' not in self.manager.user_config['tasks']
        assert 'test' not in self.manager.config['tasks']


# TODO: Finish tests