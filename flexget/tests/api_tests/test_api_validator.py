from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json


class TestValidator(object):
    config = '{tasks: {}}'

    def test_invalid_payload(self, api_client):
        new_task = {
            'name': 'new_task',
            'config': {
                'invalid_plugin': [{'title': 'entry 1'}],
                'fake_plugin2': {'url': 'http://test/rss'},
            },
        }

        rsp = api_client.json_post('/tasks/', data=json.dumps(new_task))

        assert rsp.status_code == 422
        data = json.loads(rsp.get_data(as_text=True))
        assert data.get('status_code') == 422
        assert data.get('message') == 'validation error'
        assert data.get('validation_errors')
        assert 'The keys' in data['validation_errors'][0]['message']
        assert 'invalid_plugin' in data['validation_errors'][0]['message']
        assert 'fake_plugin2' in data['validation_errors'][0]['message']
