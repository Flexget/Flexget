from datetime import datetime, timedelta

from flexget.api.app import base_message
from flexget.components.status.api import ObjectsContainer as OC
from flexget.components.status.db import StatusTask, TaskExecution
from flexget.manager import Session
from flexget.utils import json


class TestStatusAPI:
    config = "{'tasks': {}}"

    def test_status_get_all(self, api_client, schema_match):
        rsp = api_client.get('/status/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_status_list_schema, data)
        assert not errors

        with Session() as session:
            st1 = StatusTask()
            st1.name = 'status task 1'

            st2 = StatusTask()
            st2.name = 'status task 2'
            session.bulk_save_objects([st1, st2])

        rsp = api_client.get('/status/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_status_list_schema, data)
        assert not errors

        assert len(data) == 2

    def test_status_get_by_id(self, api_client, schema_match):
        rsp = api_client.get('/status/1/')
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        with Session() as session:
            st1 = StatusTask()
            st1.name = 'status task 1'

            st2 = StatusTask()
            st2.name = 'status task 2'
            session.bulk_save_objects([st1, st2])

        rsp = api_client.get('/status/1/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.task_status_schema, data)
        assert not errors

        assert data['name'] == 'status task 1'

    def test_status_executions(self, api_client, schema_match):
        rsp = api_client.get('/status/1/executions/')
        assert rsp.status_code == 404
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        with Session() as session:
            st1 = StatusTask()
            st1.name = 'status task 1'
            session.add(st1)

        rsp = api_client.get('/status/1/executions/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.executions_list, data)
        assert not errors

        assert data == []

        with Session() as session:
            st1 = session.query(StatusTask).one()

            ex1 = TaskExecution()
            ex1.start = datetime.now() - timedelta(hours=1)
            ex1.task = st1
            ex1.produced = 1
            ex1.rejected = 1
            ex1.accepted = 1
            ex1.failed = 1
            ex1.end = datetime.now()

        rsp = api_client.get('/status/1/executions/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.executions_list, data)
        assert not errors

        assert len(data) == 1


class TestTaskStatusPagination:
    config = "'tasks': {}"

    def test_status_tasks_pagination(self, api_client, link_headers):
        number_of_entries = 200

        for i in range(number_of_entries):
            with Session() as session:
                st = StatusTask()
                st.name = 'status task %s' % i
                session.add(st)

        rsp = api_client.get('/status/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/status/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/status/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_status_tasks_sorting(self, api_client):
        base_name = 'test task '
        base_start_time = datetime.now() - timedelta(days=7)

        hours = 10
        for i in range(3):
            with Session() as session:
                st = StatusTask()
                st.name = base_name + str(i)
                session.add(st)

                for ix in range(2):
                    ex1 = TaskExecution()
                    ex1.task = st
                    ex1.start = base_start_time + timedelta(hours=hours)
                    hours -= 1

        # Default sorting - Last execution time desc
        rsp = api_client.get('/status/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['name'] == 'test task 0'

        rsp = api_client.get('/status/?order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['name'] == 'test task 2'

        # Sort by name
        rsp = api_client.get('/status/?sort_by=name')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['name'] == 'test task 2'

        rsp = api_client.get('/status/?sort_by=name&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['name'] == 'test task 0'

    def test_executions_pagination(self, api_client, link_headers):
        base_start_time = datetime.now() - timedelta(days=7)
        number_of_entries = 200

        with Session() as session:
            st1 = StatusTask()
            st1.name = 'status task 1'
            session.add(st1)

            for i in range(number_of_entries):
                ex = TaskExecution()
                ex.task = st1
                ex.produced = i
                ex.rejected = i
                ex.accepted = i
                ex.start = base_start_time + timedelta(hours=i)
                ex.end = datetime.now()

        rsp = api_client.get('/status/1/executions/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/status/1/executions/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/status/1/executions/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_executions_sorting(self, api_client):
        ex1 = dict(
            start=datetime.now() - timedelta(days=7),
            end=datetime.now() - timedelta(days=6),
            produced=10,
            accepted=5,
            rejected=2,
            failed=0,
        )

        ex2 = dict(
            start=datetime.now() - timedelta(days=2),
            end=datetime.now() - timedelta(days=1),
            produced=1,
            accepted=50,
            rejected=7,
            failed=8,
            succeeded=True,
            abort_reason='test reason 1',
        )

        ex3 = dict(
            start=datetime.now() - timedelta(days=365),
            end=datetime.now() - timedelta(days=300),
            produced=2,
            accepted=1,
            rejected=3,
            failed=5,
            succeeded=False,
            abort_reason='test reason 2',
        )

        with Session() as session:
            st1 = StatusTask()
            st1.name = 'status task 1'
            session.add(st1)

            for e in [ex1, ex2, ex3]:
                db_e = TaskExecution()
                db_e.task = st1

                for k, v in e.items():
                    setattr(db_e, k, v)

        # Default sort - by start
        rsp = api_client.get('/status/1/executions/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['produced'] == 1

        rsp = api_client.get('/status/1/executions/?order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['produced'] == 10

        rsp = api_client.get('/status/1/executions/?sort_by=end')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['produced'] == 1

        rsp = api_client.get('/status/1/executions/?sort_by=end&order=asc')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['produced'] == 10
