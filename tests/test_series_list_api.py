# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import

from builtins import *  # pylint: disable=unused-import, redefined-builtin
import pytest

from flexget.utils import json


class TestSeriesListAPI(object):
    config = 'tasks: {}'

    def test_series_list_lists(self, api_client):
        rsp = api_client.get('/series_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Named param
        rsp = api_client.get('/series_list/?name=name')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        test1 = {'name': 'test1'}
        test2 = {'name': 'test2'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(test1))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('name') == 'test1'

        rsp = api_client.json_post('/series_list/', data=json.dumps(test2))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('name') == 'test2'

        rsp = api_client.get('/series_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert len(json.loads(rsp.get_data(as_text=True)).get('series_lists')) == 2

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
        # Create list
        payload = {'name': 'name'}

        rsp = api_client.json_post('/series_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get non existent list
        rsp = api_client.get('/series_list/1/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('series') == []

        series = {'title': 'title'}

        # Add series to list
        rsp = api_client.json_post('/series_list/1/series/', data=json.dumps(series))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('title') == 'title'

        series = {'title': 'series 1',
                  'alternate_name': ['SER1', 'SER2'],
                  'name_regexp': ["^ser", "^series 1$"],
                  'ep_regexp': ["^ser", "^series 1$"],
                  'date_regexp': ["^ser", "^series 1$"],
                  'sequence_regexp': ["^ser", "^series 1$"],
                  'id_regexp': ["^ser", "^series 1$"],
                  'date_yearfirst': True,
                  'date_dayfirst': True,
                  'quality': '720p',
                  'qualities': ['720p', '1080p'],
                  'timeframe': '2 days',
                  'upgrade': True,
                  'target': '1080p',
                  'propers': True,
                  'specials': True,
                  'tracking': False,
                  'identified_by': "ep",
                  'exact': True,
                  'begin': 's01e01',
                  'from_group': ['group1', 'group2'],
                  'parse_only': True}

        rsp = api_client.json_post('/series_list/1/series/', data=json.dumps(series))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        response = json.loads(rsp.get_data(as_text=True))
        for attribute in series:
            assert series[attribute] == response[attribute]

        rsp = api_client.get('/series_list/1/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert len(json.loads(rsp.get_data(as_text=True)).get('series')) == 2

    def test_series_list_series_with_identifiers(self, api_client):
        # Get non existent list
        rsp = api_client.get('/series_list/1/series/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        series = {'title': 'title',
                  'tvmaze_id': 1234,
                  'trakt_show_id': 555,
                  'tvdb_id': 666,
                  'unknown': 999}

        # Add series to list
        rsp = api_client.json_post('/series_list/1/series/', data=json.dumps(series))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        response = json.loads(rsp.get_data(as_text=True))
        for identifier in response.get('series_list_identifiers'):
            # Only recognized series identifiers will be added
            assert not identifier['id_name'] == 'unknown'
            assert series[identifier['id_name']] == identifier['id_value']

    def test_series_list_series_id(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/series_list/1/series/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        series = {'title': 'title'}

        # Add series to list
        rsp = api_client.json_post('/series_list/1/series/', data=json.dumps(series))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('title') == 'title'

        rsp = api_client.get('/series_list/1/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.delete('/series_list/1/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/series_list/1/series/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

    def test_series_list_edit_series_id(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/series_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        series = {'title': 'test_series'}

        # Add series to list
        rsp = api_client.json_post('/series_list/1/series/', data=json.dumps(series))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        assert json.loads(rsp.get_data(as_text=True)).get('title') == 'test_series'

        new_data = {'alternate_name': ['SER1', 'SER2'],
                    'name_regexp': ["^ser", "^series 1$"],
                    'ep_regexp': ["^ser", "^series 1$"],
                    'date_regexp': ["^ser", "^series 1$"],
                    'sequence_regexp': ["^ser", "^series 1$"],
                    'id_regexp': ["^ser", "^series 1$"],
                    'date_yearfirst': True,
                    'date_dayfirst': True,
                    'quality': '720p',
                    'qualities': ['720p', '1080p'],
                    'timeframe': '2 days',
                    'upgrade': True,
                    'target': '1080p',
                    'propers': True,
                    'specials': True,
                    'tracking': False,
                    'identified_by': "ep",
                    'exact': True,
                    'begin': 's01e01',
                    'from_group': ['group1', 'group2'],
                    'parse_only': True}

        rsp = api_client.json_put('/series_list/1/series/1/', data=json.dumps(new_data))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        response1 = json.loads(rsp.get_data(as_text=True))
        assert response1.get('title') == 'test_series'
        for attribute in new_data:
            assert new_data[attribute] == response1[attribute]

        rsp = api_client.get('/series_list/1/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        response2 = json.loads(rsp.get_data(as_text=True))
        assert response1 == response2
