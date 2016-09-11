from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.api import base_message
from mock import patch
from flexget.manager import Manager
from flexget.utils import json
from flexget.plugins.api.schedule import ObjectsContainer as OC


class TestScheduledAPI(object):
    config = """
            schedules:
              - tasks:
                  - test1
                interval:
                  minutes: 15
            tasks:
              test1:
                rss:
                  url: http://test/rss
                mock:
                  - title: entry 1
              test2:
                rss:
                  url: http://test/rss2
                mock:
                  - title: entry 2

            """

    def test_schedules_get(self, api_client, schema_match):
        rsp = api_client.get('/schedules/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedules_list, data)
        assert not errors

    @patch.object(Manager, 'save_config')
    def test_schedules_post(self, mocked_save_config, api_client, schema_match):
        payload = {
            'tasks': 'test2',
            'interval': {'minutes': 10}
        }
        rsp = api_client.json_post('/schedules/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.schedule_object, data)
        assert not errors
        assert mocked_save_config.called