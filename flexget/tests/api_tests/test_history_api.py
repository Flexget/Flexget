from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

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

    def test_history_pagination(self, api_client, schema_match, link_headers):
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
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        rsp = api_client.get('/history/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert len(data) == 100
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

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

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

        # Non existent page
        rsp = api_client.get('/history/?page=5')
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_history_sorting(self, api_client, schema_match, link_headers):
        history_entry1 = dict(task='test_task_1', title='test_title_a', url='test_url_1', filename='test_filename_a',
                              details='test_details_1')

        history_entry2 = dict(task='test_task_2', title='test_title_b', url='test_url_2', filename='test_filename_b',
                              details='test_details_2')

        history_entry3 = dict(task='test_task_3', title='test_title_c', url='test_url_3', filename='test_filename_c',
                              details='test_details_3')

        entries = [history_entry1, history_entry2, history_entry3]

        with Session() as session:
            for entry in entries:
                item = History()
                for key, value in entry.items():
                    setattr(item, key, value)
                session.add(item)

        rsp = api_client.get('/history/?sort_by=id')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data[0]['id'] == 3
        assert int(rsp.headers['total-count']) == 3
        assert int(rsp.headers['count']) == 3

        rsp = api_client.get('/history/?sort_by=task&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data[0]['task'] == 'test_task_1'

        rsp = api_client.get('/history/?sort_by=details')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data[0]['details'] == 'test_details_3'

        rsp = api_client.get('/history/?per_page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert len(data) == 2
        assert int(rsp.headers['total-count']) == 3
        assert int(rsp.headers['count']) == 2

        rsp = api_client.get('/history/?per_page=2&page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert len(data) == 1
        assert int(rsp.headers['total-count']) == 3
        assert int(rsp.headers['count']) == 1
