from __future__ import unicode_literals, division, absolute_import

from datetime import datetime
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.plugins.api.rejected import ObjectsContainer as OC
from flexget.plugins.filter.remember_rejected import RememberEntry, RememberTask
from flexget.utils import json
from flexget.utils.tools import parse_timedelta


def add_rejected_entry(entry):
    with Session() as session:
        task = RememberTask(name='rejected API test')
        session.add(task)
        session.commit()
        expires = datetime.now() + parse_timedelta('1 hours')
        session.add(
            RememberEntry(title=entry['test_title'], url=entry['test_url'], task_id=task.id,
                          rejected_by=entry['rejected_by'], reason=entry['reason'], expires=expires))
        session.commit()


class TestRejectedAPI(object):
    config = "{'tasks': {}}"

    entry = dict(test_title='test_title', test_url='test_url', rejected_by='rejected API test', reason='test_reason')

    def test_rejected_get_all_empty(self, api_client, schema_match):
        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.rejected_entries_list_object, data)
        assert not errors

    def test_rejected_get_all(self, api_client, schema_match):
        add_rejected_entry(self.entry)

        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.rejected_entries_list_object, data)
        assert not errors

        errors = schema_match(OC.rejected_entry_object, data['rejected_entries'][0])
        assert not errors

        values = {
            'id': 1,
            'title': self.entry['test_title'],
            'url': self.entry['test_url'],
            'rejected_by': self.entry['rejected_by'],
            'reason': self.entry['reason']
        }

        for field, value in values.items():
            assert data['rejected_entries'][0].get(field) == value

    def test_rejected_delete_all(self, api_client, schema_match):
        add_rejected_entry(self.entry)

        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.rejected_entry_object, data['rejected_entries'][0])
        assert not errors

        rsp = api_client.delete('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        assert data == {'status': 'success',
                        'message': 'successfully deleted 1 rejected entries'}

    def test_rejected_get_entry(self, api_client, schema_match):
        add_rejected_entry(self.entry)

        rsp = api_client.get('/rejected/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.rejected_entry_object, data)
        assert not errors

        values = {
            'id': 1,
            'title': self.entry['test_title'],
            'url': self.entry['test_url'],
            'rejected_by': self.entry['rejected_by'],
            'reason': self.entry['reason']
        }

        for field, value in values.items():
            assert data.get(field) == value

    def test_rejected_delete_entry(self, api_client, schema_match):
        add_rejected_entry(self.entry)

        rsp = api_client.get('/rejected/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.rejected_entry_object, data)
        assert not errors

        rsp = api_client.delete('/rejected/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        assert data == {'status': 'success',
                        'message': 'successfully deleted rejected entry 1'}
