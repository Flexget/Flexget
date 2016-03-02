from flexget.utils import json
from tests.test_api import APITest


class TestUserAPI(APITest):
    def test_change_password(self, execute_task):
        weak_password = {'password': 'weak'}
        medium_password = {'password': 'a.better.password'}
        strong_password = {'password': 'AVer123y$ron__g-=PaW[]rd'}

        rsp = self.json_put('/user/', data=json.dumps(weak_password))
        assert rsp.status_code == 500

        rsp = self.json_put('/user/', data=json.dumps(medium_password))
        assert rsp.status_code == 200

        rsp = self.json_put('/user/', data=json.dumps(strong_password))
        assert rsp.status_code == 200

    def test_change_token(self, execute_task):
        rsp = self.get('user/token/')
        assert rsp.status_code == 200
