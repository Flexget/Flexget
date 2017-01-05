# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
from flexget.api.app import base_message

from flexget.api.plugins.trakt_lookup import ObjectsContainer as oc
from flexget.utils import json


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

    def test_trakt_series_lookup_with_year_param(self, api_client, schema_match):
        values = {
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
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_trakt_slug_id_param(self, api_client, schema_match):
        values = {
            'id': 75481,
            'title': 'The Flash',
            'tvdb_id': 272094,
            'year': 1967
        }

        rsp = api_client.get('/trakt/series/the flash/?trakt_slug=the-flash-1967')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(oc.series_return_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_tmdb_id_param(self, api_client, schema_match):
        values = {
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
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_imdb_id_param(self, api_client):
        values = {
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
        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_tvdb_id_param(self, api_client, schema_match):
        values = {
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
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_tvrage_id_param(self, api_client, schema_match):
        values = {
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
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_trakt_id_param(self, api_client, schema_match):
        values = {
            'id': 75481,
            'title': 'The Flash',
            'year': 1967
        }

        rsp = api_client.get('/trakt/series/the flash/?trakt_id=75481')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_series_lookup_with_actors_param(self, api_client, schema_match):
        rsp = api_client.get('/trakt/series/the x-files/?include_actors=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        assert 'actors' in data
        assert len(data['actors']) > 0

    def test_trakt_series_lookup_with_translations_param(self, api_client, schema_match):
        rsp = api_client.get('/trakt/series/game of thrones/?include_translations=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.series_return_object, data)
        assert not errors

        assert 'translations' in data

    def test_trakt_series_lookup_error(self, api_client, schema_match):
        rsp = api_client.get('/trakt/series/sdfgsdfgsdfgsdfgsdfg/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors


@pytest.mark.online
class TestTraktMovieLookupAPI(object):
    config = 'tasks: {}'

    def test_trakt_movies_lookup_no_params(self, api_client, schema_match):
        # Bad API call
        rsp = api_client.get('/trakt/movies/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/trakt/movies/the matrix/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_return_object, data)
        assert not errors

        values = {
            'id': 481,
            'title': 'The Matrix',
            'year': 1999,
            'tmdb_id': 603,
            'imdb_id': 'tt0133093'
        }
        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_movies_lookup_year_param(self, api_client, schema_match):
        rsp = api_client.get('/trakt/movies/the matrix/?year=2003')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_return_object, data)
        assert not errors

        values = {
            'id': 483,
            'title': 'The Matrix Revolutions',
            'year': 2003,
            'tmdb_id': 605,
            'imdb_id': 'tt0242653'
        }
        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_movies_lookup_slug_param(self, api_client, schema_match):
        rsp = api_client.get('/trakt/movies/the matrix/?trakt_slug=the-matrix-reloaded-2003')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_return_object, data)
        assert not errors

        values = {
            'id': 482,
            'title': 'The Matrix Reloaded',
            'year': 2003,
            'tmdb_id': 604,
            'imdb_id': 'tt0234215'
        }
        for field, value in values.items():
            assert data.get(field) == value

    def test_trakt_movies_lookup_actors_params(self, api_client, schema_match):
        rsp = api_client.get('/trakt/movies/the matrix/?include_actors=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_return_object, data)
        assert not errors

        values = {
            'id': 481,
            'title': 'The Matrix',
            'year': 1999,
            'tmdb_id': 603,
            'imdb_id': 'tt0133093'
        }
        for field, value in values.items():
            assert data.get(field) == value

        assert 'actors' in data
        assert len(data['actors']) > 0

    def test_trakt_movies_lookup_translations_params(self, api_client, schema_match):
        rsp = api_client.get('/trakt/movies/the matrix/?include_translations=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_return_object, data)
        assert not errors

        values = {
            'id': 481,
            'title': 'The Matrix',
            'year': 1999,
            'tmdb_id': 603,
            'imdb_id': 'tt0133093'
        }
        for field, value in values.items():
            assert data.get(field) == value

        assert 'translations' in data
        assert len(data['translations']) > 0

    def test_trakt_movies_lookup_error(self, api_client, schema_match):
        rsp = api_client.get('/trakt/movies/sdfgsdfgsdfgsdfgsdfg/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors
