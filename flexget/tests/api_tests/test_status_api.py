from __future__ import unicode_literals, division, absolute_import

from datetime import datetime, timedelta

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.api.app import base_message

from flexget.manager import Session
from flexget.api.plugins.status import ObjectsContainer as OC
from flexget.plugins.operate.status import StatusTask, TaskExecution
from flexget.utils import json


class TestStatusAPI(object):
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
