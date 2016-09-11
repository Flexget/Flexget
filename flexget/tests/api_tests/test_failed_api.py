from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.api import base_message

from flexget.manager import Session
from flexget.plugins.filter.retry_failed import FailedEntry
from flexget.utils import json
from flexget.plugins.api.failed import ObjectsContainer as OC


class TestRetryFailedAPI(object):
    config = "{'tasks': {}}"

    def test_retry_failed_all(self, api_client, schema_match):
        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.retry_entries_list_object, data)
        assert not errors

        failed_entry_dict_1 = dict(title='Failed title1', url='http://123.com', reason='Test reason1')
        failed_entry_dict_2 = dict(title='Failed title2', url='http://124.com', reason='Test reason2')
        failed_entry_dict_3 = dict(title='Failed title3', url='http://125.com', reason='Test reason3')
        failed_entries = [failed_entry_dict_1, failed_entry_dict_2, failed_entry_dict_3]

        with Session() as session:
            failed_entry1 = FailedEntry(**failed_entry_dict_1)
            failed_entry2 = FailedEntry(**failed_entry_dict_2)
            failed_entry3 = FailedEntry(**failed_entry_dict_3)
            session.bulk_save_objects([failed_entry1, failed_entry2, failed_entry3])
            session.commit()

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.retry_entries_list_object, data)
        assert not errors
        for idx, entry in enumerate(data):
            for key, value in entry.items():
                data[idx].get(key) == failed_entries[idx].get(key)

        rsp = api_client.delete('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert json.loads(rsp.get_data(as_text=True)) == []

    def test_retry_failed_by_id(self, api_client, schema_match):
        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        failed_entry_dict_1 = dict(title='Failed title1', url='http://123.com', reason='Test reason1')

        with Session() as session:
            failed_entry = FailedEntry(**failed_entry_dict_1)
            session.add(failed_entry)
            session.commit()

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.retry_failed_entry_object, data)
        assert not errors
        for key, value in failed_entry_dict_1.items():
            assert data.get(key) == failed_entry_dict_1.get(key)

        rsp = api_client.delete('/failed/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors