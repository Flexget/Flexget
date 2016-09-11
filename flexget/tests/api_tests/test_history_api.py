from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from datetime import datetime
from flexget.api import base_message

from flexget.manager import Session
from flexget.plugins.output.history import History
from flexget.utils import json
from flexget.plugins.api.history import ObjectsContainer as OC


class TestHistoryAPI(object):
    config = "{'tasks': {}}"

    def test_history(self, api_client, schema_match):
        rsp = api_client.get('/history/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        assert data['entries'] == []

        history_entry_1 = dict(task='test_task1', title='test_title1', url='test_url1', filename='test_filename1',
                               details='test_details1')
        history_entry_2 = dict(task='test_task2', title='test_title2', url='test_url1', filename='test_filename1',
                               details='test_details1')

        history_entries = [history_entry_1, history_entry_2]

        with Session() as session:
            item1 = History()
            item2 = History()
            for key, value in history_entry_1.items():
                setattr(item1, key, value)
            for key, value in history_entry_2.items():
                setattr(item2, key, value)
            session.bulk_save_objects([item1, item2])
            session.commit()

        rsp = api_client.get('/history/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.history_list_object, data)
        assert not errors

        for idx, entry in enumerate(history_entries):
            for key, value in entry.items():
                assert data['entries'][idx][key] == history_entries[idx][key]
