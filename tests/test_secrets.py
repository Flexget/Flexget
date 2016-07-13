from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.event import fire_event
from flexget.utils import json
from flexget.manager import Session
from flexget.plugins.modify.config_secrets import Secrets


@pytest.mark.usefixtures('tmpdir')
class TestSecretsFromFile(object):
    config = """
        secrets: __tmp__/secret.yml
        tasks:
          test_secret_from_file:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{{ secrets.test_secret }}': accept

    """

    @pytest.mark.filecopy('secret.yml', '__tmp__/secret.yml')
    def test_secret_from_file(self, execute_task, manager):
        task = execute_task('test_secret_from_file')
        assert len(task.accepted) == 1


class TestSecretsFromDB(object):
    config = """
        secrets: yes
        tasks:
          test_secret_from_db:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{{ secrets.test_secret_db }}': accept

    """

    def test_secret_from_db(self, execute_task, manager):
        with Session() as session:
            s = Secrets(secrets={'test_secret_db': True})
            session.add(s)

        fire_event('manager.before_config_validate', manager.config, manager)

        task = execute_task('test_secret_from_db')
        assert len(task.accepted) == 1


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
