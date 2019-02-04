from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.components.variables.variables import Variables
from flexget.utils import json


class TestVariablesAPI(object):
    config = 'tasks: {}'

    variables_dict = {'test_variable_db': True}

    def test_variables_get(self, api_client):
        with Session() as session:
            s = Variables(variables=self.variables_dict)
            session.add(s)

        rsp = api_client.get('/variables/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == self.variables_dict

    def test_variables_put(self, api_client):
        rsp = api_client.get('/variables/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == {}

        rsp = api_client.json_put('/variables/', data=json.dumps(self.variables_dict))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == self.variables_dict

        rsp = api_client.get('/variables/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == self.variables_dict
