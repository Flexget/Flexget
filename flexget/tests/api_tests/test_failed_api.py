from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import copy

from flexget.api.app import base_message
from flexget.api.plugins.failed import ObjectsContainer as OC
from flexget.manager import Session
from flexget.plugins.filter.retry_failed import FailedEntry
from flexget.utils import json


class TestRetryFailedAPI(object):
    config = "{'tasks': {}}"

    def test_retry_failed_all(self, api_client, schema_match):
        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.retry_entries_list_object, data)
        assert not errors

        failed_entry_dict_1 = dict(title='Failed title1', url='http://123.com', reason='Test reason1')
        failed_entry_dict_2 = dict(title='Failed title2', url='http://124.com', reason='Test reason2')
        failed_entry_dict_3 = dict(title='Failed title3', url='http://125.com', reason='Test reason3')
        failed_entries = sorted([failed_entry_dict_1, failed_entry_dict_2, failed_entry_dict_3],
                                key=lambda x: x['title'])

        with Session() as session:
            failed_entry1 = FailedEntry(**failed_entry_dict_1)
            failed_entry2 = FailedEntry(**failed_entry_dict_2)
            failed_entry3 = FailedEntry(**failed_entry_dict_3)
            session.bulk_save_objects([failed_entry1, failed_entry2, failed_entry3])
            session.commit()

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.retry_entries_list_object, data)
        assert not errors

        # Sorted for result comparison
        data = sorted(data, key=lambda x: x['title'])
        for idx, entry in enumerate(failed_entries):
            for key, value in entry.items():
                assert data[idx].get(key) == failed_entries[idx].get(key)

        rsp = api_client.delete('/failed/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200

        assert json.loads(rsp.get_data(as_text=True)) == []

    def test_retry_failed_by_id(self, api_client, schema_match):
        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        failed_entry_dict_1 = dict(title='Failed title1', url='http://123.com', reason='Test reason1')

        with Session() as session:
            failed_entry = FailedEntry(**failed_entry_dict_1)
            session.add(failed_entry)
            session.commit()

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.retry_failed_entry_object, data)
        assert not errors
        for key, value in failed_entry_dict_1.items():
            assert data.get(key) == failed_entry_dict_1.get(key)

        rsp = api_client.delete('/failed/1/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/failed/1/')
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestFailedPaginationAPI(object):
    config = 'tasks: {}'

    def add_failed_entries(self):
        base_failed_entry = dict(title='Failed title_', url='http://123.com/', reason='Test reason_')
        num_of_entries = 200

        with Session() as session:
            for i in range(num_of_entries):
                failed_entry = copy.deepcopy(base_failed_entry)
                for key in failed_entry:
                    failed_entry[key] += str(i)
                session.add(FailedEntry(**failed_entry))

    def test_failed_pagination(self, api_client, link_headers):
        self.add_failed_entries()

        # Default values
        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/failed/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/failed/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_failed_sorting(self, api_client):
        failed_entry_dict_1 = dict(title='Failed title_1', url='http://jhb.com', reason='Test reason_3')
        failed_entry_dict_2 = dict(title='Failed title_2', url='http://def.com', reason='Test reason_1')
        failed_entry_dict_3 = dict(title='Failed title_3', url='http://abc.com', reason='Test reason_2')

        with Session() as session:
            failed_entry1 = FailedEntry(**failed_entry_dict_1)
            failed_entry2 = FailedEntry(**failed_entry_dict_2)
            failed_entry3 = FailedEntry(**failed_entry_dict_3)
            session.bulk_save_objects([failed_entry1, failed_entry2, failed_entry3])

        # Sort by title
        rsp = api_client.get('/failed/?sort_by=title')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'Failed title_3'

        rsp = api_client.get('/failed/?sort_by=title&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'Failed title_1'

        # Sort by url
        rsp = api_client.get('/failed/?sort_by=url')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['url'] == 'http://jhb.com'

        rsp = api_client.get('/failed/?sort_by=url&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['url'] == 'http://abc.com'

        # Sort by reason
        rsp = api_client.get('/failed/?sort_by=reason')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['reason'] == 'Test reason_3'

        rsp = api_client.get('/failed/?sort_by=reason&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['reason'] == 'Test reason_1'

        # Combine sorting and pagination
        rsp = api_client.get('/failed/?sort_by=reason&per_page=2&page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['reason'] == 'Test reason_1'
