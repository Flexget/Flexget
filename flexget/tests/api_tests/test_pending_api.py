from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from flexget.api.app import base_message
from flexget.entry import Entry

from flexget.utils import json
from flexget.plugins.filter.pending_approval import PendingEntry
from flexget.api.plugins.pending import ObjectsContainer as OC
from flexget.manager import Session


class TestPendingAPI(object):
    config = "{'tasks': {}}"

    def test_pending_api_get_all(self, api_client, schema_match):
        rsp = api_client.get('/pending/')
        assert rsp.status_code == 200

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_list, data)
        assert not errors

        e1 = Entry(title='test.title1', url='http://bla.com')
        e2 = Entry(title='test.title1', url='http://bla.com')

        with Session() as session:
            pe1 = PendingEntry('test_task', e1)
            pe2 = PendingEntry('test_task', e2)
            session.bulk_save_objects([pe1, pe2])

        rsp = api_client.get('/pending/')
        assert rsp.status_code == 200

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_list, data)
        assert not errors
        assert len(data) == 2
        assert all(e['approved'] is False for e in data)

    def test_pending_api_put_all(self, api_client, schema_match):
        e1 = Entry(title='test.title1', url='http://bla.com')
        e2 = Entry(title='test.title1', url='http://bla.com')

        with Session() as session:
            pe1 = PendingEntry('test_task', e1)
            pe2 = PendingEntry('test_task', e2)
            session.bulk_save_objects([pe1, pe2])

        payload = {'operation': 'approve'}

        rsp = api_client.json_put('/pending/', data=json.dumps(payload))
        assert rsp.status_code == 201

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_list, data)
        assert not errors

        assert len(data) == 2
        assert all(e['approved'] is True for e in data)

        rsp = api_client.json_put('/pending/', data=json.dumps(payload))
        assert rsp.status_code == 204

        payload = {'operation': 'reject'}

        rsp = api_client.json_put('/pending/', data=json.dumps(payload))
        assert rsp.status_code == 201

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_list, data)
        assert not errors

        assert len(data) == 2
        assert all(e['approved'] is False for e in data)

        rsp = api_client.json_put('/pending/', data=json.dumps(payload))
        assert rsp.status_code == 204

    def test_pending_api_delete_all(self, api_client, schema_match):
        e1 = Entry(title='test.title1', url='http://bla.com')
        e2 = Entry(title='test.title1', url='http://bla.com')

        with Session() as session:
            pe1 = PendingEntry('test_task', e1)
            pe2 = PendingEntry('test_task', e2)
            session.bulk_save_objects([pe1, pe2])

        rsp = api_client.delete('/pending/')
        assert rsp.status_code == 200

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_pending_api_get_entry(self, api_client, schema_match):
        e1 = Entry(title='test.title1', url='http://bla.com')
        e2 = Entry(title='test.title1', url='http://bla.com')

        with Session() as session:
            pe1 = PendingEntry('test_task', e1)
            pe2 = PendingEntry('test_task', e2)
            session.bulk_save_objects([pe1, pe2])

        rsp = api_client.get('/pending/1/')
        assert rsp.status_code == 200

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_object, data)
        assert not errors

        assert data['approved'] is False

    def test_pending_api_put_entry(self, api_client, schema_match):
        e1 = Entry(title='test.title1', url='http://bla.com')
        e2 = Entry(title='test.title1', url='http://bla.com')

        with Session() as session:
            pe1 = PendingEntry('test_task', e1)
            pe2 = PendingEntry('test_task', e2)
            session.bulk_save_objects([pe1, pe2])

        payload = {'operation': 'approve'}

        rsp = api_client.json_put('/pending/1/', data=json.dumps(payload))
        assert rsp.status_code == 201

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_object, data)
        assert not errors

        assert data['approved'] is True

        rsp = api_client.json_put('/pending/1/', data=json.dumps(payload))
        assert rsp.status_code == 400

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload = {'operation': 'reject'}

        rsp = api_client.json_put('/pending/1/', data=json.dumps(payload))
        assert rsp.status_code == 201

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pending_entry_object, data)
        assert not errors

        assert data['approved'] is False

        rsp = api_client.json_put('/pending/1/', data=json.dumps(payload))
        assert rsp.status_code == 400

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_pending_api_delete_entry(self, api_client, schema_match):
        e1 = Entry(title='test.title1', url='http://bla.com')
        e2 = Entry(title='test.title1', url='http://bla.com')

        with Session() as session:
            pe1 = PendingEntry('test_task', e1)
            pe2 = PendingEntry('test_task', e2)
            session.bulk_save_objects([pe1, pe2])

        rsp = api_client.delete('/pending/1/')
        assert rsp.status_code == 200

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/pending/1/')
        assert rsp.status_code == 404

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
