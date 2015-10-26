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
            couchpotato:
              base_url: 'http://test.url.com'
              port: 5050
              api_key: '123abc'
        """

    @mock.patch('flexget.plugins.input.couchpotato.CouchPotato.get_json')
    def test_couchpotato_sanity(self, mock_get):
        mock_get.return_value = movie_list_response

        self.execute_task('couch')

        assert mock_get.called, 'Did not access Couchpotato results.'
        assert len(self.task._all_entries) == 31, 'Did not produce 31 entries'
        for entry in self.task._all_entries:
            assert entry.store['quality_req'] == '', 'Quality for entry {} should be empty, instead its {}'.format(
                entry['title'], entry.store['quality_req'])
