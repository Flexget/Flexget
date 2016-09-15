from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

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
            session.commit()

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

        for idx, value in enumerate(sorted(data['seen_entries'], key=lambda entry: entry['title'])):
            for k, v in entries[idx].items():
                assert value[k] == v

        assert data['total_number_of_seen_entries'] == len(data['seen_entries']) == 2

        rsp = api_client.get('/seen/?local=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert data['total_number_of_seen_entries'] == len(data['seen_entries']) == 1

        rsp = api_client.get('/seen/?value=test_value_2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert data['total_number_of_seen_entries'] == len(data['seen_entries']) == 1

        rsp = api_client.get('/seen/?value=bla')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        assert data['total_number_of_seen_entries'] == len(data['seen_entries']) == 0

    def test_seen_delete_all(self, api_client, schema_match):
        entries = self.add_seen_entries()

        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seen_search_object, data)
        assert not errors

        for idx, value in enumerate(sorted(data['seen_entries'], key=lambda entry: entry['title'])):
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

        assert data['seen_entries'] == []

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

        assert len(data['seen_entries']) == 1

        rsp = api_client.delete('/seen/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
