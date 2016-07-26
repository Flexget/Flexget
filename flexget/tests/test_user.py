from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.utils import json


class TestUserAPI(object):
    config = 'tasks: {}'

    def test_change_password(self, execute_task, api_client):
        weak_password = {'password': 'weak'}
        medium_password = {'password': 'a.better.password'}
        strong_password = {'password': 'AVer123y$ron__g-=PaW[]rd'}

        rsp = api_client.json_put('/user/', data=json.dumps(weak_password))
        assert rsp.status_code == 500

        rsp = api_client.json_put('/user/', data=json.dumps(medium_password))
        assert rsp.status_code == 200

        rsp = api_client.json_put('/user/', data=json.dumps(strong_password))
        assert rsp.status_code == 200

    def test_change_token(self, execute_task, api_client):
        rsp = api_client.get('user/token/')
        assert rsp.status_code == 200
