from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.plugins.filter.retry_failed import FailedEntry
from flexget.utils import json


class TestRetryFailedAPI(object):
    config = "{'tasks': {}}"

    def test_retry_failed_get_all(self, api_client):
        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert json.loads(rsp.get_data(as_text=True))['number_of_failed_entries'] == 0

        with Session() as session:
            failed_entry = FailedEntry(title='Failed title', url='http://123.com', reason='Test reason')
            session.add(failed_entry)
            session.commit()

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert json.loads(rsp.get_data(as_text=True))['number_of_failed_entries'] == 1

    def test_retry_failed_delete_all(self, api_client):
        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert json.loads(rsp.get_data(as_text=True))['number_of_failed_entries'] == 0

        with Session() as session:
            failed_entry = FailedEntry(title='Failed title', url='http://123.com', reason='Test reason')
            session.add(failed_entry)
            session.commit()

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert json.loads(rsp.get_data(as_text=True))['number_of_failed_entries'] == 1

        rsp = api_client.delete('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/failed/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True))['number_of_failed_entries'] == 0

    def test_retry_failed_get_by_id(self, api_client):
        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        with Session() as session:
            failed_entry = FailedEntry(title='Failed title', url='http://123.com', reason='Test reason')
            session.add(failed_entry)
            session.commit()

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    def test_retry_failed_delete_by_id(self, api_client):
        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        with Session() as session:
            failed_entry = FailedEntry(title='Failed title', url='http://123.com', reason='Test reason')
            session.add(failed_entry)
            session.commit()

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.delete('/failed/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/failed/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
