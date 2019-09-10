from __future__ import unicode_literals, division, absolute_import

import copy
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.api.app import base_message
from flexget.components.managed_lists.lists.movie_list.api import ObjectsContainer as OC
from flexget.components.managed_lists.lists.movie_list.db import (
    MovieListBase,
    MovieListList,
    MovieListMovie,
)
from flexget.components.managed_lists.lists.movie_list.movie_list import MovieListBase
from flexget.manager import Session
from flexget.utils import json


class TestMovieListAPI(object):
    config = 'tasks: {}'

    def test_movie_list_list(self, api_client, schema_match):
        # No params
        rsp = api_client.get('/movie_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_lists, data)
        assert not errors

        assert data == []

        # Named param
        rsp = api_client.get('/movie_list/?name=name')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_lists, data)
        assert not errors

        payload = {'name': 'test'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.list_object, data)
        assert not errors

        values = {'name': 'test', 'id': 1}
        for field, value in values.items():
            assert data.get(field) == value

        rsp = api_client.get('/movie_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_lists, data)
        assert not errors

        for field, value in values.items():
            assert data[0].get(field) == value

        # Try to Create existing list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

    def test_movie_list_list_id(self, api_client, schema_match):
        payload = {'name': 'test'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.list_object, data)
        assert not errors

        values = {'name': 'test', 'id': 1}
        for field, value in values.items():
            assert data.get(field) == value

        # Get list
        rsp = api_client.get('/movie_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.list_object, data)
        assert not errors

        values = {'name': 'test', 'id': 1}
        for field, value in values.items():
            assert data.get(field) == value

        # Delete list
        rsp = api_client.delete('/movie_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        # Get non existent list
        rsp = api_client.get('/movie_list/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        # Delete non existent list
        rsp = api_client.delete('/movie_list/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

    def test_movie_list_movies(self, api_client, schema_match):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        movie_data = {'movie_name': 'title'}

        # Add movie to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        movie = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, movie)
        assert not errors

        # Get movies from list
        rsp = api_client.get('/movie_list/1/movies/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_movies, data)
        assert not errors

        assert data[0] == movie

        # Get movies from non-existent list
        rsp = api_client.get('/movie_list/10/movies/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

    def test_movie_list_movies_with_identifiers(self, api_client, schema_match):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        identifier = {'imdb_id': 'tt1234567'}
        movie_data = {'movie_name': 'title', 'movie_identifiers': [identifier]}

        # Add movie to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, data)
        assert not errors

        # Get movies from list
        rsp = api_client.get('/movie_list/1/movies/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_movies, data)
        assert not errors

        returned_identifier = data[0]['movies_list_ids'][0]
        assert returned_identifier['id_name'], (
            returned_identifier['id_value'] == identifier.items()[0]
        )

        # Add movie to non-existent list
        rsp = api_client.json_post('/movie_list/10/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        non_valid_identifier = {'bla': 'tt1234567'}
        movie_data = {'movie_name': 'title2', 'movie_identifiers': [non_valid_identifier]}

        # Add movie with invalid identifier to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

    def test_movie_list_movie(self, api_client, schema_match):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        identifier = {'imdb_id': 'tt1234567'}
        movie_data = {'movie_name': 'title', 'movie_identifiers': [identifier]}

        # Add movie to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get specific movie from list
        rsp = api_client.get('/movie_list/1/movies/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, data)
        assert not errors

        returned_identifier = data['movies_list_ids'][0]
        assert returned_identifier['id_name'], (
            returned_identifier['id_value'] == identifier.items()[0]
        )

        identifiers = [{'trakt_movie_id': '12345'}]

        # Change specific movie from list
        rsp = api_client.json_put('/movie_list/1/movies/1/', data=json.dumps(identifiers))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, data)
        assert not errors

        returned_identifier = data['movies_list_ids'][0]
        assert returned_identifier['id_name'], (
            returned_identifier['id_value'] == identifiers[0].items()
        )

        # PUT non-existent movie from list
        rsp = api_client.json_put('/movie_list/1/movies/10/', data=json.dumps(identifiers))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        non_valid_identifier = [{'bla': 'tt1234567'}]
        # Change movie using invalid identifier from list
        rsp = api_client.json_put('/movie_list/1/movies/1/', data=json.dumps(non_valid_identifier))
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        # Delete specific movie from list
        rsp = api_client.delete('/movie_list/1/movies/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match({'type': 'object'}, data)
        assert not errors

        # Get non existent movie from list
        rsp = api_client.get('/movie_list/1/movies/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        # Delete non existent movie from list
        rsp = api_client.delete('/movie_list/1/movies/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code


class TestMovieListUseCases(object):
    config = 'tasks: {}'

    def test_adding_same_movie(self, api_client, schema_match):
        payload = {'name': 'test'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.list_object, data)
        assert not errors

        movie = {'movie_name': 'test movie', 'movie_year': 2000}

        # Add movie to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, data)
        assert not errors

        # Try to add it again
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(base_message, data)
        assert not errors

        movie_2 = copy.deepcopy(movie)
        movie_2['movie_year'] = 1999

        # Add same movie name, different year
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_2))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, data)
        assert not errors

        movie_3 = copy.deepcopy(movie)
        del movie_3['movie_year']

        # Add same movie, no year
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_3))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.movie_list_object, data)
        assert not errors

    def test_identifiers(self, api_client, schema_match):
        rsp = api_client.get('/movie_list/identifiers/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_identifiers, data)
        assert not errors

        identifiers = MovieListBase().supported_ids
        assert data == identifiers


class TestMovieListPagination(object):
    config = 'tasks: {}'

    def test_movie_list_pagination(self, api_client, link_headers):
        base_movie = dict(title='title_', year=1900)
        number_of_movies = 200

        with Session() as session:
            movie_list = MovieListList(name='test_list')
            session.add(movie_list)

            for i in range(number_of_movies):
                movie = copy.deepcopy(base_movie)
                movie['title'] += str(i)
                movie['year'] += i
                movie_list.movies.append(MovieListMovie(**movie))

        # Default values
        rsp = api_client.get('/movie_list/1/movies/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/movie_list/1/movies/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('/movie_list/1/movies/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_movie_list_sorting(self, api_client):
        with Session() as session:
            movie_list = MovieListList(name='test_list')
            session.add(movie_list)

            movie_list.movies.append(MovieListMovie(title='movie a', year=2005))
            movie_list.movies.append(MovieListMovie(title='movie b', year=2004))
            movie_list.movies.append(MovieListMovie(title='movie c', year=2003))

        # Sort by title
        rsp = api_client.get('/movie_list/1/movies/?sort_by=title')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'movie c'

        rsp = api_client.get('/movie_list/1/movies/?sort_by=title&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['title'] == 'movie a'

        # Sort by year
        rsp = api_client.get('/movie_list/1/movies/?sort_by=year')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['year'] == 2005

        rsp = api_client.get('/movie_list/1/movies/?sort_by=year&order=asc')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['year'] == 2003

        # Combine sorting and pagination
        rsp = api_client.get('/movie_list/1/movies/?sort_by=year&per_page=2&page=2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert data[0]['year'] == 2003
