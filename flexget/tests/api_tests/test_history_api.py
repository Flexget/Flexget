from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.api.app import base_message

from flexget.api.plugins.history import ObjectsContainer as OC
from flexget.manager import Session
from flexget.plugins.output.history import History
from flexget.utils import json


class TestHistoryAPI(object):
    config = "{'tasks': {}}"

    def test_history(self, api_client, schema_match):
        rsp = api_client.get('/history/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data == []

        history_entry = dict(task='test_task1', title='test_title1', url='test_url1', filename='test_filename1',
                             details='test_details1')

        with Session() as session:
            item = History()
            for key, value in history_entry.items():
                setattr(item, key, value)
            session.add(item)
            session.commit()

        rsp = api_client.get('/history/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        for key, value in history_entry.items():
            assert data[0][key] == value

        rsp = api_client.get('/history/?task=test_task1')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        for key, value in history_entry.items():
            assert data[0][key] == value

        rsp = api_client.get('/history/?task=bla')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data == []


class TestHistoryPaginationAPI(object):
    config = "{'tasks': {}}"

    def test_history_pagination(self, api_client, schema_match):
        history_entry = dict(task='test_task_', title='test_title_', url='test_url_', filename='test_filename_',
                             details='test_details_')
        num_of_entries = 200

        with Session() as session:
            for i in range(num_of_entries):
                item = History()
                for key, value in history_entry.items():
                    setattr(item, key, value + str(i))
                session.add(item)

        rsp = api_client.get('/history/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert len(data) == 50  # Default page size

        rsp = api_client.get('/history/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert len(data) == 100

        # Per page is limited to 100
        rsp = api_client.get('/history/?per_page=200')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert len(data) == 100

        rsp = api_client.get('/history/?page=2&sort_by=id&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data[0]['task'] == 'test_task_50'

        rsp = api_client.get('/history/?page=5')
        assert rsp.status_code == 400
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
