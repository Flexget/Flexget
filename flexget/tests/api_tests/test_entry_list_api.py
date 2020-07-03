import copy

from flexget.api.app import base_message
from flexget.components.managed_lists.lists.entry_list.api import ObjectsContainer as OC
from flexget.components.managed_lists.lists.entry_list.db import EntryListEntry, EntryListList
from flexget.entry import Entry
from flexget.manager import Session
from flexget.utils import json


class TestEntryListAPI:
    config = 'tasks: {}'

    def test_entry_list_list(self, api_client, schema_match):
        # No params
        rsp = api_client.get('/entry_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_return_lists, data)
        assert not errors

        payload = {'name': 'test_list'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_base_object, data)
        assert not errors

        for field, value in payload.items():
            assert data.get(field) == value

        # Named param
        rsp = api_client.get('/entry_list/?name=test_list')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_return_lists, data)
        assert not errors

        for field, value in payload.items():
            assert data[0].get(field) == value

        # Try to Create list again
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_entry_list_list_id(self, api_client, schema_match):
        payload = {'name': 'test_list'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_base_object, data)
        assert not errors

        for field, value in payload.items():
            assert data.get(field) == value

        # Get list
        rsp = api_client.get('/entry_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_base_object, data)
        assert not errors

        for field, value in payload.items():
            assert data.get(field) == value

        # Delete list
        rsp = api_client.delete('/entry_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Try to get list
        rsp = api_client.get('/entry_list/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Try to Delete list
        rsp = api_client.delete('/entry_list/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_entry_list_entries(self, api_client, schema_match):
        # Get non existent list
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload = {'name': 'test_list'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_base_object, data)
        assert not errors

        for field, value in payload.items():
            assert data.get(field) == value

        entry_data = {'title': 'title', 'original_url': 'http://test.com'}

        # Add entry to list
        rsp = api_client.json_post('/entry_list/1/entries/', data=json.dumps(entry_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_entry_base_object, data)
        assert not errors

        for field, value in entry_data.items():
            assert data.get(field) == value

        # Get entries from list
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_lists_entries_return_object, data)
        assert not errors

        for field, value in entry_data.items():
            assert data[0].get(field) == value

        # Try to re-add entry to list
        rsp = api_client.json_post('/entry_list/1/entries/', data=json.dumps(entry_data))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_entry_base_object, data)
        assert not errors

        # Try to post to non existing list
        rsp = api_client.json_post('/entry_list/10/entries/', data=json.dumps(entry_data))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_entry_base_object, data)
        assert not errors

    def test_entry_list_entry(self, api_client, schema_match):
        payload = {'name': 'test_list'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_base_object, data)
        assert not errors

        for field, value in payload.items():
            assert data.get(field) == value

        entry_data = {'title': 'title', 'original_url': 'http://test.com'}

        # Add entry to list
        rsp = api_client.json_post('/entry_list/1/entries/', data=json.dumps(entry_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_entry_base_object, data)
        assert not errors

        for field, value in entry_data.items():
            assert data.get(field) == value

        # Get entries from list
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_lists_entries_return_object, data)
        assert not errors

        for field, value in entry_data.items():
            assert data[0].get(field) == value

        # Get specific entry from list
        rsp = api_client.get('/entry_list/1/entries/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_entry_base_object, data)
        assert not errors

        for field, value in entry_data.items():
            assert data.get(field) == value

        new_entry_data = {'title': 'title2', 'original_url': 'http://test2.com'}

        # Change specific entry from list
        rsp = api_client.json_put('/entry_list/1/entries/1/', data=json.dumps(new_entry_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_list_entry_base_object, data)
        assert not errors

        for field, value in new_entry_data.items():
            assert data.get(field) == value

        # Try to change non-existent entry from list
        rsp = api_client.json_put('/entry_list/1/entries/10/', data=json.dumps(new_entry_data))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Delete specific entry from list
        rsp = api_client.delete('/entry_list/1/entries/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Get non existent entry from list
        rsp = api_client.get('/entry_list/1/entries/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Delete non existent entry from list
        rsp = api_client.delete('/entry_list/1/entries/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_entry_list_entries_batch_remove(self, api_client, schema_match):
        payload = {'name': 'test_list'}

        # Create list
        api_client.json_post('/entry_list/', data=json.dumps(payload))

        # Add 3 entries to list
        for i in range(3):
            payload = {'title': f'title {i}', 'original_url': f'http://{i}test.com'}
            rsp = api_client.json_post('/entry_list/1/entries/', data=json.dumps(payload))
            assert rsp.status_code == 201

        # get entries is correct
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_lists_entries_return_object, data)
        assert not errors
        assert len(data) == 3

        payload = {'ids': [1, 2, 3]}

        rsp = api_client.json_delete('entry_list/1/entries/batch', data=json.dumps(payload))
        assert rsp.status_code == 204

        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.entry_lists_entries_return_object, data)
        assert not errors
        assert not data


class TestEntryListPagination:
    config = 'tasks: {}'

    def test_entry_list_pagination(self, api_client, link_headers):
        base_entry = dict(title='test_title_', original_url='url_')
        number_of_entries = 200

        with Session() as session:
            entry_list = EntryListList(name='test list')
            session.add(entry_list)

            for i in range(number_of_entries):
                entry = copy.deepcopy(base_entry)
                for k, v in entry.items():
                    entry[k] = v + str(i)
                e = Entry(entry)
                entry_list.entries.append(EntryListEntry(e, entry_list.id))

        # Default values
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/entry_list/1/entries/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/entry_list/1/entries/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_entry_list_sorting(self, api_client):
        base_entry_1 = dict(title='test_title_1', original_url='url_c')
        base_entry_2 = dict(title='test_title_2', original_url='url_b')
        base_entry_3 = dict(title='test_title_3', original_url='url_a')

        with Session() as session:
            entry_list = EntryListList(name='test list')
            session.add(entry_list)

            e1 = Entry(base_entry_1)
            e2 = Entry(base_entry_2)
            e3 = Entry(base_entry_3)

            entry_list.entries.append(EntryListEntry(e1, entry_list.id))
            entry_list.entries.append(EntryListEntry(e2, entry_list.id))
            entry_list.entries.append(EntryListEntry(e3, entry_list.id))

        # Sort by title
        rsp = api_client.get('/entry_list/1/entries/?sort_by=title')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_3'

        rsp = api_client.get('/entry_list/1/entries/?sort_by=title&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_1'

        # Sort by original url
        rsp = api_client.get('/entry_list/1/entries/?sort_by=original_url')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['original_url'] == 'url_c'

        rsp = api_client.get('/entry_list/1/entries/?sort_by=original_url&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['original_url'] == 'url_a'

        # Combine sorting and pagination
        rsp = api_client.get('/entry_list/1/entries/?sort_by=title&per_page=2&page=2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_1'
