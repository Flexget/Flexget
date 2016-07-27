from __future__ import unicode_literals, division, absolute_import

from datetime import datetime
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.plugins.api.rejected import rejected_entry_object, rejected_entries_list_object
from flexget.plugins.filter.remember_rejected import RememberEntry, RememberTask
from flexget.utils import json
from flexget.utils.tools import parse_timedelta


class TestRejectedAPI(object):
    config = "{'tasks': {}}"

    def test_rejected_get_all_empty(self, api_client, schema_match):
        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(rejected_entries_list_object, data)
        assert not errors

    def test_rejected_get_all(self, api_client, schema_match):
        test_title = 'test_title'
        test_url = 'test_url'
        rejected_by = 'rejected API test'
        reason = 'test_reason'

        with Session() as session:
            task = RememberTask(name='rejected API test')
            session.add(task)
            session.commit()
            expires = datetime.now() + parse_timedelta('1 hours')
            session.add(
                RememberEntry(title=test_title, url=test_url, task_id=task.id, rejected_by=rejected_by,
                              reason=reason, expires=expires))
            session.commit()

        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(rejected_entries_list_object, data)
        assert not errors

        errors = schema_match(rejected_entry_object, data['rejected_entries'][0])
        assert not errors

        values = {
            'id': 1,
            'title': test_title,
            'url': test_url,
            'rejected_by': rejected_by,
            'reason': reason
        }

        for field, value in values.items():
            assert data['rejected_entries'][0].get(field) == value


