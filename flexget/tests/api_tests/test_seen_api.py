from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import copy

from flexget.api.app import base_message
from flexget.api.plugins.seen import ObjectsContainer as OC
from flexget.manager import Session
from flexget.plugins.filter.seen import SeenEntry, SeenField
from flexget.utils import json


class TestSeenAPI(object):
    config = "{'tasks': {}}"

    def add_seen_entries(self):
        seen_entry_1 = dict(title='test_title', reason='test_reason', task='test_task')
        field_1 = dict(field='test_field_1', value='test_value_1')
        field_2 = dict(field='test_field_2', value='test_value_2')
        seen_entry_2 = dict(title='test_title_2', reason='test_reason_2', task='test_task_2', local=True)
        field_3 = dict(field='test_field_3', value='test_value_3')
        field_4 = dict(field='test_field_4', value='test_value_4')

        entries = sorted([seen_entry_1, seen_entry_2], key=lambda entry: entry['title'])

        with Session() as session:
            seen_db_1 = SeenEntry(**seen_entry_1)
            seen_db_1.fields = [SeenField(**field_1), SeenField(**field_2)]
            session.add(seen_db_1)
            seen_db_2 = SeenEntry(**seen_entry_2)
            seen_db_2.fields = [SeenField(**field_3), SeenField(**field_4)]
            session.add(seen_db_2)

        return entries

    def test_seen_get_all(self, api_client, schema_match):
        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        entries = self.add_seen_entries()

        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        for idx, value in enumerate(sorted(data, key=lambda entry: entry['title'])):
            for k, v in entries[idx].items():
                assert value[k] == v

        assert len(data) == 2

        rsp = api_client.get('/seen/?local=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert len(data) == 1

        rsp = api_client.get('/seen/?value=test_value_2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert len(data) == 1

        rsp = api_client.get('/seen/?value=bla')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert len(data) == 0

    def test_seen_delete_all(self, api_client, schema_match):
        entries = self.add_seen_entries()

        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        for idx, value in enumerate(sorted(data, key=lambda entry: entry['title'])):
            for k, v in entries[idx].items():
                assert value[k] == v

        rsp = api_client.delete('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        assert data['message'] == 'successfully deleted 2 entries'

        self.add_seen_entries()

        rsp = api_client.delete('/seen/?local=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        assert data['message'] == 'successfully deleted 1 entries'

        rsp = api_client.delete('/seen/?value=test_value_2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        assert data['message'] == 'successfully deleted 1 entries'

        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert data == []

    def test_seen_get_by_id(self, api_client, schema_match):
        entries = self.add_seen_entries()

        rsp = api_client.get('/seen/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_object, data)
        assert not errors

        for key, value in entries[0].items():
            assert data[key] == value

        rsp = api_client.get('/seen/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_seen_get_delete_id(self, api_client, schema_match):
        self.add_seen_entries()

        rsp = api_client.delete('/seen/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert len(data) == 1

        rsp = api_client.delete('/seen/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeenPagination(object):
    config = 'tasks: {}'

    def test_seen_pagination(self, api_client, link_headers):
        base_seen_entry = dict(title='test_title_', task='test_task_', reason='test_reason_')
        base_seen_field = dict(field='test_field_', value='test_value_')
        number_of_entries = 200

        with Session() as session:
            for i in range(number_of_entries):
                entry = copy.deepcopy(base_seen_entry)
                field = copy.deepcopy(base_seen_field)

                for key, value in entry.items():
                    entry[key] = value + str(i)

                for key, value in field.items():
                    field[key] = value + str(i)

                seen_entry = SeenEntry(**entry)
                session.add(seen_entry)
                seen_entry.fields = [SeenField(**field)]

        # Default values
        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/seen/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/seen/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_seen_sorting(self, api_client):
        seen_entry_1 = dict(title='test_title_1', reason='test_reason_c', task='test_task_2', local=True)
        field_1 = dict(field='test_field_1', value='test_value_1')
        field_2 = dict(field='test_field_2', value='test_value_2')
        seen_entry_2 = dict(title='test_title_2', reason='test_reason_b', task='test_task_3', local=True)
        field_3 = dict(field='test_field_3', value='test_value_3')
        field_4 = dict(field='test_field_4', value='test_value_4')
        seen_entry_3 = dict(title='test_title_3', reason='test_reason_a', task='test_task_1', local=False)
        field_5 = dict(field='test_field_3', value='test_value_3')
        field_6 = dict(field='test_field_4', value='test_value_4')

        with Session() as session:
            seen_db_1 = SeenEntry(**seen_entry_1)
            session.add(seen_db_1)
            seen_db_1.fields = [SeenField(**field_1), SeenField(**field_2)]

            seen_db_2 = SeenEntry(**seen_entry_2)
            session.add(seen_db_2)
            seen_db_2.fields = [SeenField(**field_3), SeenField(**field_4)]

            seen_db_3 = SeenEntry(**seen_entry_3)
            session.add(seen_db_3)
            seen_db_3.fields = [SeenField(**field_5), SeenField(**field_6)]

        # Sort by title
        rsp = api_client.get('/seen/?sort_by=title')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_3'

        rsp = api_client.get('/seen/?sort_by=title&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_1'

        # Sort by task
        rsp = api_client.get('/seen/?sort_by=task')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['task'] == 'test_task_3'

        rsp = api_client.get('/seen/?sort_by=task&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['task'] == 'test_task_1'

        # Sort by reason
        rsp = api_client.get('/seen/?sort_by=reason')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['reason'] == 'test_reason_c'

        rsp = api_client.get('/seen/?sort_by=reason&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['reason'] == 'test_reason_a'

        # Sort by local
        rsp = api_client.get('/seen/?sort_by=local')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['local'] == True

        rsp = api_client.get('/seen/?sort_by=local&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['local'] == False

        # Combine sorting and pagination
        rsp = api_client.get('/seen/?sort_by=reason&per_page=2&page=2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['reason'] == 'test_reason_a'
