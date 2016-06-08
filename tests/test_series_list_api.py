# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import

from builtins import *  # pylint: disable=unused-import, redefined-builtin
import pytest

from flexget.utils import json


class TestSeriesListAPI(object):
    config = 'tasks: {}'

    def test_series_list_list(self, api_client):
        rsp = api_client.get('/series_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Named param
        rsp = api_client.get('/series_list/?name=name')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = {'name': 'test'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

    def test_series_list_list_id(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get list
        rsp = api_client.get('/series_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Delete list
        rsp = api_client.delete('/series_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    def test_series_list_series(self, api_client):
        # Get non existent list
        rsp = api_client.get('/series_list/1/series/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        series = {'title': 'title'}

        # Add series to list
        rsp = api_client.json_post('/series_list/1/series/', data=json.dumps(series))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('title') == 'title'