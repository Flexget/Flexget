from __future__ import unicode_literals, division, absolute_import
from builtins import *

from mock import patch

from flexget.manager import Session
from flexget.plugins.filter import seen
from flexget.plugins.filter.seen import SeenEntry, SeenField
from flexget.utils import json


class TestSeenAPI(object):

    config = 'tasks: {}'

    @patch.object(seen, 'search')
    def test_seen_get(self, mock_seen_search, api_client):

        def search(*args, **kwargs):
            if 'count' in kwargs:
                return 0
            else:
                with Session() as session:
                    return session.query(SeenEntry).join(SeenField)

        mock_seen_search.side_effect = search

        # No params
        rsp = api_client.get('/seen/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Default params
        rsp = api_client.get('/seen/?page=1&max=100&local_seen=true&sort_by=added&order=desc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Changed params
        rsp = api_client.get('/seen/?max=1000&local_seen=false&sort_by=title&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Negative test, invalid parameter
        rsp = api_client.get('/seen/?max=1000&local_seen=BLA&sort_by=title &order=asc')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        # With value
        rsp = api_client.get('/seen/?value=bla')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert mock_seen_search.call_count == 8, 'Should have 8 calls, is actually %s' % mock_seen_search.call_count

    @patch.object(seen, 'forget_by_id')
    def test_delete_seen_entry(self, mock_forget, api_client):
        rsp = api_client.delete('/seen/1234')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_cod
        assert mock_forget.called

    def test_seen_add(self, execute_task, api_client):
        fields = {
            'url': 'http://test.com/file.torrent',
            'title': 'Test.Title',
            'torrent_hash_id': 'dsfgsdfg34tq34tq34t'
        }
        entry = {
            'local': False,
            'reason': 'test_reason',
            'task': 'test_task',
            'title': 'Test.Title',
            'fields': fields
        }

        rsp = api_client.json_post('/seen/', data=json.dumps(entry))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    @patch.object(seen, 'search')
    def test_seen_delete_all(self, mock_seen_search, api_client):
        session = Session()
        entry_list = session.query(SeenEntry).join(SeenField)
        mock_seen_search.return_value = entry_list

        # No params
        rsp = api_client.delete('/seen/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        fields = {
            'url': 'http://test.com/file.torrent',
            'title': 'Test.Title',
            'torrent_hash_id': 'dsfgsdfg34tq34tq34t'
        }
        entry = {
            'local': False,
            'reason': 'test_reason',
            'task': 'test_task',
            'title': 'Test.Title',
            'fields': fields
        }

        rsp = api_client.json_post('/seen/', data=json.dumps(entry))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # With value
        rsp = api_client.delete('/seen/?value=Test.Title')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert mock_seen_search.call_count == 2, 'Should have 2 calls, is actually %s' % mock_seen_search.call_count