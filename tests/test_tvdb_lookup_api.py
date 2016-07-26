# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import

import copy

from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.utils import json


@pytest.mark.online
class TestTVDBLookupAPI(object):
    config = 'tasks: {}'

    series_schema = {
        "type": "object",
        "properties": {
            "airs_dayofweek": {"type": "string"},
            "airs_time": {"type": "string"},
            "aliases": {"type": "array", "items": {"type": "string"}},
            "banner": {"type": "string"},
            "content_rating": {"type": "string"},
            "expired": {"type": "boolean"},
            "first_aired": {"type": "string"},
            "genres": {"type": "array", "items": {"type": "string"}},
            "imdb_id": {"type": "string"},
            "language": {"type": "string"},
            "last_updated": {"type": "string"},
            "network": {"type": "string"},
            "overview": {"type": "string"},
            "posters": {"type": "array", "items": {"type": "string"}},
            "rating": {"type": "number"},
            "runtime": {"type": "integer"},
            "series_name": {"type": "string"},
            "status": {"type": "string"},
            "tvdb_id": {"type": "integer"},
            "zap2it_id": {"type": "string"}
        },
        "required": [
            "airs_dayofweek",
            "airs_time",
            "aliases",
            "banner",
            "content_rating",
            "expired",
            "first_aired",
            "genres",
            "imdb_id",
            "language",
            "last_updated",
            "network",
            "overview",
            "posters",
            "rating",
            "runtime",
            "series_name",
            "status",
            "tvdb_id",
            "zap2it_id"
        ]
    }
    series_schema_actors = copy.deepcopy(series_schema)
    series_schema_actors.update({'properties': {"actors": {"type": "array", "items": {"type": "string"}}}})
    series_schema_actors['required'].append('actors')
    episode_schema = {
        "type": "object",
        "properties": {
            "absolute_number": {"type": ["null", "integer"]},
            "director": {"type": "string"},
            "episode_name": {"type": "string"},
            "episode_number": {"type": "integer"},
            "expired": {"type": "boolean"},
            "first_aired": {"type": "string"},
            "id": {"type": "integer"},
            "image": {"type": "string"},
            "last_update": {"type": "integer"},
            "overview": {"type": "string"},
            "rating": {"type": "number"},
            "season_number": {"type": "integer"},
            "series_id": {"type": "integer"}
        },
        "required": ["absolute_number", "director", "episode_name", "episode_number", "expired", "first_aired",
                     "id", "image", "last_update", "overview", "rating", "season_number", "series_id"]
    }
    search_results_schema = {
        "type": "object",
        "properties": {
            "search_results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "banner": {"type": ["string", "null"]},
                        "first_aired": {"type": "string"},
                        "network": {"type": "string"},
                        "overview": {"type": ["string", "null"]},
                        "series_name": {"type": "string"},
                        "status": {"type": "string"},
                        "tvdb_id": {"type": "integer"}
                    },
                    "required": ["aliases", "banner", "first_aired", "network", "overview", "series_name", "status",
                                 "tvdb_id"]}}
        },
        "required": [
            "search_results"
        ]
    }

    def test_tvdb_series_lookup(self, api_client, schema_match):
        values = {
            'tvdb_id': 77398,
            'imdb_id': 'tt0106179',
            'language': 'en',
            'series_name': 'The X-Files',
            'zap2it_id': 'EP00080955'
        }

        rsp = api_client.get('/tvdb/series/The X-Files/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(self.series_schema, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_tvdb_series_lookup_with_actors(self, api_client, schema_match):
        values = {
            'tvdb_id': 77398,
            'imdb_id': 'tt0106179',
            'language': 'en',
            'series_name': 'The X-Files',
            'zap2it_id': 'EP00080955'
        }

        rsp = api_client.get('/tvdb/series/The X-Files/?include_actors=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(self.series_schema_actors, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_tvdb_episode_lookup_season_and_ep_number(self, api_client, schema_match):
        rsp = api_client.get('/tvdb/episode/77398/')
        assert rsp.status_code == 500, 'Response code is %s' % rsp.status_code

        values = {
            'episode_number': 6,
            'id': 5313345,
            'season_number': 10,
            'series_id': 77398,
            'absolute_number': None
        }

        rsp = api_client.get('/tvdb/episode/77398/?season_number=10&ep_number=6')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(self.episode_schema, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_tvdb_episode_lookup_by_absolute_number(self, api_client, schema_match):
        values = {
            'episode_number': 23,
            'id': 5598674,
            'season_number': 2,
            'series_id': 279121,
            'absolute_number': 46
        }

        rsp = api_client.get('/tvdb/episode/279121/?absolute_number=46')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(self.episode_schema, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_tvdb_search_results_by_name(self, api_client, schema_match):

        rsp = api_client.get('/tvdb/search/?search_name=supernatural')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(self.search_results_schema, data)
        assert not errors

        values = {
            'series_name': "Supernatural",
            'tvdb_id': 78901
        }

        for field, value in values.items():
            assert data['search_results'][0].get(field) == value

    def test_tvdb_search_results_by_imdb_id(self, api_client, schema_match):

        rsp = api_client.get('/tvdb/search/?imdb_id=tt0944947')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(self.search_results_schema, data)
        assert not errors

        values = {
            'series_name': "Game of Thrones",
            'tvdb_id': 121361
        }

        for field, value in values.items():
            assert data['search_results'][0].get(field) == value

    def test_tvdb_search_results_by_zap2it_id(self, api_client, schema_match):

        rsp = api_client.get('/tvdb/search/?zap2it_id=EP01922936')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(self.search_results_schema, data)
        assert not errors

        values = {
            'series_name': "The Flash (2014)",
            'tvdb_id': 279121
        }

        for field, value in values.items():
            assert data['search_results'][0].get(field) == value
