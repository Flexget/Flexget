from __future__ import unicode_literals, division, absolute_import
import json
import mock
from tests import FlexGetBase

movie_list_file = 'couchpotoato_movie_list_test_response.json'
qualities_profiles_file = 'couchpotoato_quality_profile_test_response.json'

with open(movie_list_file, "r") as data:
    movie_list_response = json.load(data)

with open(qualities_profiles_file, "r") as data:
    qualities_response = json.load(data)


class TestCouchpotatoSanity(FlexGetBase):
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


class TestCouchpotatoQuality(FlexGetBase):
    __yaml__ = """
        tasks:
          couch:
            couchpotato:
              base_url: 'http://test.url.com'
              port: 5050
              api_key: '123abc'
              include_data: yes
        """

    def quality_assertion(self, entry, expected_quality):
        assert entry['quality_req'] == expected_quality, \
            'Expected Quality for entry {} should be {}, instead its {}'.format(entry['title'], expected_quality,
                                                                                entry.store['quality_req'])

    @mock.patch('flexget.plugins.input.couchpotato.CouchPotato.get_json')
    def test_couchpotato_quality(self, mock_get):
        mock_get.side_effect = [movie_list_response, qualities_response]
        self.execute_task('couch')

        assert mock_get.call_count == 2

        for entry in self.task._all_entries:
            if entry['title'] == 'American Ultra':
                self.quality_assertion(entry, u'720p|1080p')
            elif entry['title'] == 'Anomalisa':
                self.quality_assertion(entry, u'720p|1080p')
            elif entry['title'] == 'Ant-Man':
                self.quality_assertion(entry, u'720p')
            elif entry['title'] == 'Austin Powers 4':
                self.quality_assertion(entry, u'720p')
            elif entry['title'] == 'Black Mass':
                self.quality_assertion(entry, u'720p')
