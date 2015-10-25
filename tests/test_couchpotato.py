from __future__ import unicode_literals, division, absolute_import
import json
import mock
from tests import FlexGetBase

movie_list_file = 'couchpotoato_test_reponse.json'
with open(movie_list_file, "r") as data:
         movie_list_response = json.load(data)


class TestCouchpotato(FlexGetBase):

    __yaml__ = """
        tasks:
          couch:
            base_url: 'http://test.url.com'
            port: 5050
            api_key: '123abc'
        """

    @mock.patch('flexget.plugins.input.couchpotato.CouchPotato.get_json')
    def test_couchpotato(self, mock_get):

        mock_response = mock.Mock()
        mock_response.json.return_value = movie_list_response
        mock_get.return_value = mock_response

        self.execute_task('couch')

        assert mock_get.called



