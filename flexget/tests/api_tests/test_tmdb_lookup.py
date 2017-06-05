# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
from flexget.api.app import base_message

from flexget.api.plugins.tmdb_lookup import ObjectsContainer as oc
from flexget.utils import json


@pytest.mark.online
class TestTMDBMovieLookupAPI(object):
    config = 'tasks: {}'

    def test_tmdb_movies_lookup_by_title(self, api_client, schema_match):
        # Bad API call
        rsp = api_client.get('/tmdb/movies/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/tmdb/movies/?title=the matrix/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_object, data)
        assert not errors

        values = {
            'id': 603,
            'name': 'The Matrix',
            'year': 1999,
            'imdb_id': 'tt0133093'
        }
        for field, value in values.items():
            assert data.get(field) == value

    def test_tmdb_movies_lookup_year_param(self, api_client, schema_match):
        rsp = api_client.get('/tmdb/movies/?title=the matrix reloaded&year=2003')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_object, data)
        assert not errors

        values = {
            'id': 604,
            'name': 'The Matrix Reloaded',
            'year': 2003,
            'imdb_id': 'tt0234215'
        }
        for field, value in values.items():
            assert data.get(field) == value

    def test_tmdb_movies_lookup_posters_params(self, api_client, schema_match):
        rsp = api_client.get('/tmdb/movies/?title=the matrix&include_posters=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_object, data)
        assert not errors

        assert 'posters' in data
        assert len(data['posters']) > 0

    def test_tmdb_movies_lookup_backdrops_params(self, api_client, schema_match):
        rsp = api_client.get('/tmdb/movies/?title=the matrix&include_backdrops=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(oc.movie_object, data)
        assert not errors

        assert 'backdrops' in data
        assert len(data['backdrops']) > 0
