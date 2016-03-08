from __future__ import unicode_literals, division, absolute_import

from flexget.utils import json


class TestMovieListAPI(object):
    config = 'tasks: {}'

    def test_movie_list_list(self, api_client):
        # No params
        rsp = api_client.get('/movie_list/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Named param
        rsp = api_client.get('/movie_list/?name=name')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

    def test_movie_list_list_id(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get list
        rsp = api_client.get('/movie_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Delete list
        rsp = api_client.delete('/movie_list/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    def test_movie_list_movies(self, api_client):
        # Get non existent list
        rsp = api_client.get('/movie_list/1/movies/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        identifier = {'imdb_id': 'tt1234567'}
        movie_data = {'title': 'title',
                      'original_url': 'http://test.com',
                      'movie_identifiers': [identifier]}

        # Add movie to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get movies from list
        rsp = api_client.get('/movie_list/1/movies/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        returned_identifier = json.loads(rsp.data)['movies'][0]['movies_list_ids'][0]
        assert returned_identifier['id_name'], returned_identifier['id_value'] == identifier.items()[0]

    def test_movie_list_movie(self, api_client):
        payload = {'name': 'name'}

        # Create list
        rsp = api_client.json_post('/movie_list/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        identifier = {'imdb_id': 'tt1234567'}
        movie_data = {'title': 'title',
                      'original_url': 'http://test.com',
                      'movie_identifiers': [identifier]}

        # Add movie to list
        rsp = api_client.json_post('/movie_list/1/movies/', data=json.dumps(movie_data))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code

        # Get movies from list
        rsp = api_client.get('/movie_list/1/movies/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        returned_identifier = json.loads(rsp.data)['movies'][0]['movies_list_ids'][0]
        assert returned_identifier['id_name'], returned_identifier['id_value'] == identifier.items()[0]

        # Get specific movie from list
        rsp = api_client.get('/movie_list/1/movies/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        returned_identifier = json.loads(rsp.data)['movies_list_ids'][0]
        assert returned_identifier['id_name'], returned_identifier['id_value'] == identifier.items()[0]

        identifiers = [{'trakt_movie_id': '12345'}]

        # Change specific movie from list
        rsp = api_client.json_put('/movie_list/1/movies/1/', data=json.dumps(identifiers))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        returned_identifier = json.loads(rsp.data)['movies_list_ids'][0]
        assert returned_identifier['id_name'], returned_identifier['id_value'] == identifiers[0].items()

        # Delete specific movie from list
        rsp = api_client.delete('/movie_list/1/movies/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Get non existent movie from list
        rsp = api_client.get('/movie_list/1/movies/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        # Delete non existent movie from list
        rsp = api_client.delete('/movie_list/1/movies/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
