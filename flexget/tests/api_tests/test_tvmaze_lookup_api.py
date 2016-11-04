# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.api.app import base_message
from flexget.api.plugins.tvmaze_lookup import ObjectsContainer as OC
from flexget.utils import json


@pytest.mark.online
class TestTVMAzeSeriesLookupAPI(object):
    config = 'tasks: {}'

    def test_tvmaze_series_lookup_by_name(self, api_client, schema_match):
        values = {
            'language': 'English',
            'name': 'The X-Files',
            'network': 'FOX',
            'show_type': 'Scripted',
            'tvdb_id': 77398,
            'tvmaze_id': 430,
            'tvrage_id': 6312,
            'url': 'http://www.tvmaze.com/shows/430/the-x-files',
            'webchannel': None,
            'year': 1993
        }

        rsp = api_client.get('/tvmaze/series/The X-Files/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.tvmaze_series_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

        rsp = api_client.get('/tvmaze/series/sdfgv35wvg23vg2/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_tvmaze_series_lookup_by_id(self, api_client, schema_match):
        rsp = api_client.get('/tvmaze/series/13/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.tvmaze_series_object, data)
        assert not errors

        values = {
            'language': 'English',
            'name': 'The Flash',
            'network': 'The CW',
            'show_type': 'Scripted',
            'tvdb_id': 279121,
            'tvmaze_id': 13,
            'tvrage_id': 36939,
            'url': 'http://www.tvmaze.com/shows/13/the-flash',
            'year': 2014
        }

        for field, value in values.items():
            assert data.get(field) == value

    def test_tvmaze_episode_by_ep_and_season(self, api_client, schema_match):
        rsp = api_client.get('/tvmaze/episode/13/?season_num=1&ep_num=1')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.tvmaze_episode_object, data)
        assert not errors

        values = {
            'number': 1,
            'runtime': 60,
            'season_number': 1,
            'series_id': 13,
            'title': 'City of Heroes',
            'tvmaze_id': 592,
            'url': 'http://www.tvmaze.com/episodes/592/the-flash-1x01-city-of-heroes'
        }

        for field, value in values.items():
            assert data.get(field) == value

    def test_tvmaze_episode_by_air_date(self, api_client, schema_match):
        rsp = api_client.get('/tvmaze/episode/3928/?air_date=2016-09-12')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.tvmaze_episode_object, data)
        assert not errors

        values = {
            'number': 113,
            'runtime': 30,
            'season_number': 2016,
            'series_id': 3928,
            'summary': '<p>Rapper T.I. Harris.</p>',
            'title': 'T.I. Harris',
            'tvmaze_id': 925421,
            'url': 'http://www.tvmaze.com/episodes/925421/the-daily-show-with-trevor-noah-2016-09-12-ti-harris'
        }

        for field, value in values.items():
            assert data.get(field) == value

        rsp = api_client.get('/tvmaze/episode/3928/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/tvmaze/episode/3928/?season_num=1')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_tvmaze_episode_lookup_error(self, api_client, schema_match):
        rsp = api_client.get('/tvmaze/episode/13/?season_num=100&ep_num=100')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
