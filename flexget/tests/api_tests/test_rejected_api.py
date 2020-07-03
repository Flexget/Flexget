import copy
from datetime import datetime

from flexget.api.app import base_message
from flexget.components.rejected.api import ObjectsContainer as OC
from flexget.components.rejected.db import RememberEntry, RememberTask
from flexget.manager import Session
from flexget.utils import json
from flexget.utils.tools import parse_timedelta


def add_rejected_entry(entry):
    with Session() as session:
        task = RememberTask(name='rejected API test')
        session.add(task)
        session.commit()

        expires = datetime.now() + parse_timedelta('1 hours')
        session.add(
            RememberEntry(
                title=entry['test_title'],
                url=entry['test_url'],
                task_id=task.id,
                rejected_by=entry['rejected_by'],
                reason=entry['reason'],
                expires=expires,
            )
        )


class TestRejectedAPI:
    config = "{'tasks': {}}"

    entry = dict(
        test_title='test_title',
        test_url='test_url',
        rejected_by='rejected API test',
        reason='test_reason',
    )

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

        errors = schema_match(OC.rejected_entry_object, data[0])
        assert not errors

        values = {
            'id': 1,
            'title': self.entry['test_title'],
            'url': self.entry['test_url'],
            'rejected_by': self.entry['rejected_by'],
            'reason': self.entry['reason'],
        }

        for field, value in values.items():
            assert data[0].get(field) == value

    def test_rejected_delete_all(self, api_client, schema_match):
        add_rejected_entry(self.entry)

        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.rejected_entry_object, data[0])
        assert not errors

        rsp = api_client.delete('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        assert data == {
            'status': 'success',
            'status_code': 200,
            'message': 'successfully deleted 1 rejected entries',
        }

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
            'reason': self.entry['reason'],
        }

        for field, value in values.items():
            assert data.get(field) == value

        rsp = api_client.get('/rejected/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

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
        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/rejected/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/rejected/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors


class TestRejectedPagination:
    config = 'tasks: {}'

    def test_rejected_pagination(self, api_client, link_headers):
        base_reject_entry = dict(
            title='test_title_', url='test_url_', rejected_by='rejected_by_', reason='reason_'
        )
        number_of_entries = 200

        with Session() as session:
            task = RememberTask(name='rejected API test')
            session.add(task)
            session.commit()

            for i in range(number_of_entries):
                r_entry = copy.deepcopy(base_reject_entry)
                for key, value in r_entry.items():
                    r_entry[key] = value + str(i)
                expires = datetime.now() + parse_timedelta('1 hours')
                session.add(RememberEntry(expires=expires, task_id=task.id, **r_entry))

        # Default values
        rsp = api_client.get('/rejected/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/rejected/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/rejected/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_rejected_sorting(self, api_client):
        expires_1 = datetime.now() + parse_timedelta('1 hours')
        expires_2 = datetime.now() + parse_timedelta('2 hours')
        expires_3 = datetime.now() + parse_timedelta('3 hours')

        reject_entry_1 = dict(
            title='test_title_1',
            url='test_url_c',
            rejected_by='rejected_by_2',
            reason='reason_3',
            expires=expires_1,
        )
        reject_entry_2 = dict(
            title='test_title_2',
            url='test_url_a',
            rejected_by='rejected_by_3',
            reason='reason_2',
            expires=expires_2,
        )
        reject_entry_3 = dict(
            title='test_title_3',
            url='test_url_b',
            rejected_by='rejected_by_1',
            reason='reason_1',
            expires=expires_3,
        )

        with Session() as session:
            task = RememberTask(name='rejected API test')
            session.add(task)
            session.commit()

            session.add(RememberEntry(task_id=task.id, **reject_entry_1))
            session.add(RememberEntry(task_id=task.id, **reject_entry_2))
            session.add(RememberEntry(task_id=task.id, **reject_entry_3))

        # Sort by title
        rsp = api_client.get('/rejected/?sort_by=title')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_3'

        rsp = api_client.get('/rejected/?sort_by=title&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_1'

        # Sort by url
        rsp = api_client.get('/rejected/?sort_by=url')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['url'] == 'test_url_c'

        rsp = api_client.get('/rejected/?sort_by=url&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['url'] == 'test_url_a'

        # Sort by expires
        rsp = api_client.get('/rejected/?sort_by=expires')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_3'

        rsp = api_client.get('/rejected/?sort_by=expires&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_1'

        # Combine sorting and pagination
        rsp = api_client.get('/rejected/?sort_by=title&per_page=2&page=2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'test_title_1'
