from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.manager import Session
from flexget.plugins.modify.config_secrets import Secrets
from flexget.utils import json


class TestSecretsAPI(object):
    config = 'tasks: {}'

    secrets_dict = {'test_secret_db': True}

    def test_secrets_get(self, api_client):
        with Session() as session:
            s = Secrets(secrets=self.secrets_dict)
            session.add(s)

        rsp = api_client.get('/secrets/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == self.secrets_dict

    def test_secrets_put(self, api_client):
        rsp = api_client.get('/secrets/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == {}

        rsp = api_client.json_put('/secrets/', data=json.dumps(self.secrets_dict))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == self.secrets_dict

        rsp = api_client.get('/secrets/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)) == self.secrets_dict
