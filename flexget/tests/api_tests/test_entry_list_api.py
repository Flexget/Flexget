from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.api import base_message

from flexget.utils import json
from flexget.plugins.api.entry_list import ObjectsContainer as OC


class TestEntryListAPI(object):
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
            assert data['entries'][0].get(field) == value

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
            assert data['entries'][0].get(field) == value

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
