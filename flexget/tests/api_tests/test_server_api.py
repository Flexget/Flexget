from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json
import os

import pytest
from mock import patch

from flexget import __version__
from flexget.api.app import __version__ as __api_version__, base_message
from flexget.api.core.server import ObjectsContainer as OC
from flexget.manager import Manager
from flexget.tests.conftest import MockManager
from flexget.utils.tools import get_latest_flexget_version_number


class TestServerAPI(object):
    config = """
        tasks:
          test:
            rss:
              url: http://test/rss
            mock:
              - title: entry 1
        """

    def test_pid(self, api_client, schema_match):
        rsp = api_client.get('/server/pid/', headers={})
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.pid_object, data)
        assert not errors
        assert data['pid'] == os.getpid()

    @patch.object(MockManager, 'load_config')
    def test_reload(self, mocked_load_config, api_client, schema_match):
        payload = {'operation': 'reload'}
        rsp = api_client.json_post('/server/manage/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
        assert mocked_load_config.called

    @patch.object(Manager, 'shutdown')
    def test_shutdown(self, mocked_shutdown, api_client, schema_match):
        payload = {'operation': 'shutdown'}
        rsp = api_client.json_post('/server/manage/', data=json.dumps(payload))
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
        assert mocked_shutdown.called

    def test_get_config(self, api_client, schema_match):
        rsp = api_client.get('/server/config/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match({'type': 'object'}, data)
        assert not errors
        assert data == {
            'tasks': {
                'test': {
                    'mock': [{'title': 'entry 1'}],
                    'rss': {
                        'url': u'http://test/rss',
                        'group_links': False,
                        'ascii': False,
                        'escape': False,
                        'silent': False,
                        'all_entries': True,
                    },
                }
            }
        }

    def test_get_raw_config(self, manager, api_client, schema_match):
        manager.config_path = os.path.join(os.path.dirname(__file__), 'raw_config.yml')

        rsp = api_client.get('/server/raw_config/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.raw_config_object, data)
        assert not errors

        assert (
            data['raw_config']
            == 'dGFza3M6CiAgdGVzdDoKICAgIHJzczoKICAgICAgdXJsOiBodHRwOi8vdGVzdC9yc3MKICAgIG1'
            'vY2s6CiAgICAgIC0gdGl0bGU6IGVudHJ5IDE='
        )

    @pytest.mark.online
    def test_version(self, api_client, schema_match):
        latest = get_latest_flexget_version_number()

        rsp = api_client.get('/server/version/')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.version_object, data)
        assert not errors
        assert data == {
            'flexget_version': __version__,
            'api_version': __api_version__,
            'latest_version': latest,
        }

    def test_crash_logs_without_crash_log(self, api_client, schema_match):
        rsp = api_client.get('/server/crash_logs')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.crash_logs, data)
        assert not errors

        assert not data

    def test_crash_logs_with_crashes(self, api_client, schema_match, manager):
        manager.config_base = os.path.join(os.path.dirname(__file__))
        rsp = api_client.get('/server/crash_logs')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.crash_logs, data)
        assert not errors

        assert len(data) == 2
