from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.utils import json


class TestEntryListAPI(object):
    config = 'tasks: {}'

    def test_entry_list_list(self, api_client):
        # No params
        rsp = api_client.get('/entry_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Named param
        rsp = api_client.get('/entry_list/?name=name')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

    def test_entry_list_list_id(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get list
        rsp = api_client.get('/entry_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Delete list
        rsp = api_client.delete('/entry_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    def test_entry_list_entries(self, api_client):
        # Get non existant list
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        entry_data = {'title': 'title', 'original_url': 'http://test.com'}

        # Add entry to list
        rsp = api_client.json_post('/entry_list/1/entries/', data=json.dumps(entry_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get entries from list
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        serialized_entry = json.loads(rsp.get_data(as_text=True))['entries'][0]['entry']
        assert serialized_entry == entry_data

    def test_entry_list_entry(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/entry_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        entry_data = {'title': 'title', 'original_url': 'http://test.com'}

        # Add entry to list
        rsp = api_client.json_post('/entry_list/1/entries/', data=json.dumps(entry_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get entries from list
        rsp = api_client.get('/entry_list/1/entries/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True))['entries'][0]['entry'] == entry_data

        # Get specific entry from list
        rsp = api_client.get('/entry_list/1/entries/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True))['entry'] == entry_data

        new_entry_data = {'title': 'title2', 'original_url': 'http://test2.com'}

        # Change specific entry from list
        rsp = api_client.json_put('/entry_list/1/entries/1/', data=json.dumps(new_entry_data))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True))['entry'] == new_entry_data

        # Delete specific entry from list
        rsp = api_client.delete('/entry_list/1/entries/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Get non existent entry from list
        rsp = api_client.get('/entry_list/1/entries/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        # Delete non existent entry from list
        rsp = api_client.delete('/entry_list/1/entries/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
