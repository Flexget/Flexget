# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
import pytest

from flexget.utils import json
from flexget.plugins.api.trakt_lookup import objects_container as oc


def check_trakt_fields(data, exact=None):
    expected_fields = [
        'air_day', 'air_time', 'first_aired', 'certification', 'country', 'genres', 'homepage',
        'id', 'images', 'imdb_id', 'language', 'network', 'overview', 'runtime', 'slug', 'timezone',
        'title', 'tmdb_id', 'tvdb_id', 'tvrage_id', 'year'
    ]

    for field in expected_fields:
        assert field in data, 'Field %s didn\'t exist in data' % field

    if exact:
        for field, value in exact.items():
            assert data.get(field) == value


@pytest.mark.online
class TestTraktSeriesLookupAPI(object):
    config = 'tasks: {}'

    def test_trakt_series_lookup_no_params(self, api_client, schema_match):
        # Bad API call
        rsp = api_client.get('/trakt/series/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/trakt/series/the x-files/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(oc.series_return_object, data)
        assert not errors

        values = {
            'id': 4063,
            'imdb_id': 'tt0106179',
            'language': 'en',
            'title': 'The X-Files',
            'tmdb_id': 4087,
            'tvdb_id': 77398,
            'tvrage_id': 6312,
            'year': 1993
        }

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_year_param(self, api_client):
        exact_match = {
            'id': 235,
            'imdb_id': 'tt0098798',
            'language': 'en',
            'title': 'The Flash',
            'tmdb_id': 236,
            'tvdb_id': 78650,
            'tvrage_id': 5781,
            'year': 1990
        }

        rsp = api_client.get('/trakt/series/the flash/?year=1990')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_trakt_slug_id_param(self, api_client):
        exact_match = {
            'id': 75481,
            'title': 'The Flash',
            'tvdb_id': 272094,
            'year': 1967
        }

        rsp = api_client.get('/trakt/series/the flash/?trakt_slug=the-flash-1967')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_tmdb_id_param(self, api_client):
        exact_match = {
            'id': 60300,
            'imdb_id': 'tt3107288',
            'title': 'The Flash',
            'tmdb_id': 60735,
            'tvdb_id': 279121,
            'tvrage_id': 36939,
            'year': 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?tmdb_id=60735')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_imdb_id_param(self, api_client):
        exact_match = {
            'id': 60300,
            'imdb_id': 'tt3107288',
            'title': 'The Flash',
            'tmdb_id': 60735,
            'tvdb_id': 279121,
            'tvrage_id': 36939,
            'year': 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?imdb_id=tt3107288')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_tvdb_id_param(self, api_client):
        exact_match = {
            'id': 60300,
            'imdb_id': 'tt3107288',
            'title': 'The Flash',
            'tmdb_id': 60735,
            'tvdb_id': 279121,
            'tvrage_id': 36939,
            'year': 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?tvdb_id=279121')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_tvrage_id_param(self, api_client):
        exact_match = {
            'id': 60300,
            'imdb_id': 'tt3107288',
            'title': 'The Flash',
            'tmdb_id': 60735,
            'tvdb_id': 279121,
            'tvrage_id': 36939,
            'year': 2014
        }

        rsp = api_client.get('/trakt/series/the flash/?tvrage_id=36939')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_trakt_id_param(self, api_client):
        exact_match = {
            'id': 75481,
            'title': 'The Flash',
            'year': 1967
        }

        rsp = api_client.get('/trakt/series/the flash/?trakt_id=75481')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        check_trakt_fields(data, exact=exact_match)

    def test_trakt_series_lookup_with_actors_param(self, api_client):
        rsp = api_client.get('/trakt/series/the x-files/?include_actors=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert 'actors' in data
        assert len(data['actors']) > 0

    def test_trakt_series_lookup_with_translations_param(self, api_client):
        rsp = api_client.get('/trakt/series/game of thrones/?include_translations=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert 'translations' in data
        assert 'bs' in data['translations']


@pytest.mark.online
class TestTraktMovieLookupAPI(object):
    config = 'tasks: {}'

    def test_trakt_movies_lookup_no_params(self, api_client):
        # Bad API call
        rsp = api_client.get('/trakt/movies/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/trakt/movies/the matrix/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        assert data.get('id') == 481
        assert data.get('year') == 1999
        assert data.get('tmdb_id') == 603
        assert data.get('imdb_id') == 'tt0133093'
