import json

from flexget.api.app import base_message
from flexget.api.core.tasks import ObjectsContainer as OC
from flexget.api.core.tasks import _apply_second_guess_metadata
from flexget.entry import Entry


class TestExecuteAPI:
    @staticmethod
    def get_task_queue(manager):
        """Be used to execute task queue."""
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
        entry = {'title': 'injected', 'url': 'http://test.com'}

        payload = {'inject': [entry], 'tasks': ['test_task']}
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
            'title': 'injected',
            'url': 'http://test.com',
            'accept': True,
            'tasks': ['test_task'],
        }

        payload = {'inject': [entry], 'tasks': ['test_task']}
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
        entry = {'title': 'accept', 'url': 'http://test.com'}

        payload = {'inject': [entry], 'tasks': ['test_task']}
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
        fields = {'imdb_id': 'tt1234567', 'tmdb_id': '1234567'}
        entry = {'title': 'injected', 'url': 'http://test.com', 'fields': fields, 'accept': True}

        payload = {'inject': [entry], 'tasks': ['test_task']}

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
        assert entry['imdb_id'] == 'tt1234567'
        assert entry['tmdb_id'] == '1234567'

    def test_multiple_entries(self, api_client, manager, schema_match):
        entry1 = {'title': 'entry1', 'url': 'http://test.com', 'accept': True}
        entry2 = {'title': 'entry2', 'url': 'http://test.com', 'accept': True}

        payload = {'inject': [entry1, entry2], 'tasks': ['test_task']}
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
        entry = {'title': 'injected', 'url': 'http://test.com', 'accept': True}

        payload = {'inject': [entry], 'tasks': ['test_task']}
        rsp = api_client.json_post('/inject/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_execution_results_schema, data)
        assert not errors

        task = self.get_task_queue(manager)
        task.execute()

        assert len(task.all_entries) == 1
        assert len(task.accepted) == 1


class TestExecuteMultipleTasks:
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


class TestSecondGuessMetadata:
    config = """
        tasks:
          test_task:
            mock:
              - title: 'TestShow - 12'
                url: 'http://test.com/show.torrent'
              - title: 'Some Movie 2024'
                url: 'http://test.com/movie.torrent'
            manipulate:
              - title:
                  replace:
                    regexp: ' - (\\d+)$'
                    format: ' S01E\\1'
            accept_all: yes
        """

    @staticmethod
    def get_task_queue(manager):
        assert len(manager.task_queue) == 1
        task = manager.task_queue.run_queue.get(timeout=0.5)
        assert task
        return task

    def test_params_contains_second_guess_metadata(self, api_client):
        rsp = api_client.get('/tasks/execute/params/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))
        assert 'second_guess_metadata' in data['properties']
        param = data['properties']['second_guess_metadata']
        assert param['type'] == 'boolean'
        assert 'description' in param

    def test_second_guess_metadata_accepted_by_schema(self, api_client, manager):
        payload = {
            'tasks': ['test_task'],
            'entry_dump': False,
            'second_guess_metadata': True,
        }
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

    def test_second_guess_metadata_unit(self, manager):
        series_entry = Entry(title='TestShow S01E12', url='http://test.com/1.torrent')
        movie_entry = Entry(title='Some Movie 2024', url='http://test.com/2.torrent')

        _apply_second_guess_metadata([series_entry, movie_entry])

        assert series_entry.get('series_name') is not None
        assert series_entry.get('series_season') == 1
        assert series_entry.get('series_episode') == 12
        assert series_entry.get('series_guessed') is True

        assert movie_entry.get('movie_name') is not None
        assert movie_entry.get('movie_year') == 2024

    def test_second_guess_metadata_does_not_overwrite_existing_series(self, manager):
        entry = Entry(title='TestShow S01E12', url='http://test.com/1.torrent')
        entry['series_name'] = 'Explicitly Set Name'
        entry['series_season'] = 5
        entry['series_episode'] = 99

        _apply_second_guess_metadata([entry])

        assert entry['series_name'] == 'Explicitly Set Name'
        assert entry['series_season'] == 5
        assert entry['series_episode'] == 99

    def test_second_guess_metadata_does_not_overwrite_existing_movie(self, manager):
        entry = Entry(title='Some Movie 2024', url='http://test.com/2.torrent')
        entry['movie_name'] = 'Explicit Movie'
        entry['movie_year'] = 1999

        _apply_second_guess_metadata([entry])

        assert entry['movie_name'] == 'Explicit Movie'
        assert entry['movie_year'] == 1999

    def test_second_guess_metadata_ignored_without_entry_dump(self, api_client, manager):
        payload = {
            'tasks': ['test_task'],
            'second_guess_metadata': True,
        }
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()
        assert len(task.all_entries) > 0

    def test_entry_dump_second_guesses_metadata_when_enabled(self, api_client, manager):
        payload = {'tasks': ['test_task'], 'entry_dump': True, 'second_guess_metadata': True}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        message = json.loads(task.stream['queue'].get(timeout=1))
        dumped = {e['title']: e for e in message['entry_dump']}
        assert dumped['TestShow S01E12'].get('series_name') is not None
        assert dumped['TestShow S01E12'].get('series_season') == 1
        assert dumped['TestShow S01E12'].get('series_episode') == 12
        assert dumped['Some Movie 2024'].get('movie_name') is not None

    def test_entry_dump_skips_second_guess_by_default(self, api_client, manager):
        payload = {'tasks': ['test_task'], 'entry_dump': True}
        rsp = api_client.json_post('/tasks/execute/', data=json.dumps(payload))
        assert rsp.status_code == 200

        task = self.get_task_queue(manager)
        task.execute()

        message = json.loads(task.stream['queue'].get(timeout=1))
        dumped = {e['title']: e for e in message['entry_dump']}
        assert dumped['TestShow S01E12'].get('series_name') is None
        assert dumped['Some Movie 2024'].get('movie_name') is None
