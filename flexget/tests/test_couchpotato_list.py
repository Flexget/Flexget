import json
import os
from unittest import mock

movie_list_file = os.path.join(
    os.path.dirname(__file__), 'couchpotato_movie_list_test_response.json'
)
qualities_profiles_file = os.path.join(
    os.path.dirname(__file__), 'couchpotato_quality_profile_test_response.json'
)

with open(movie_list_file, encoding='utf-8') as data:
    movie_list_response = json.load(data)

with open(qualities_profiles_file) as data:
    qualities_response = json.load(data)


class TestCouchpotato:
    config = """
        tasks:
          couch:
            couchpotato_list:
              base_url: 'http://test.url.com'
              port: 5050
              api_key: '123abc'
        """

    @mock.patch('flexget.components.managed_lists.lists.couchpotato_list.CouchPotatoBase.get_json')
    def test_couchpotato_no_data(self, mock_get, execute_task):
        mock_get.return_value = movie_list_response

        task = execute_task('couch')

        assert mock_get.called, 'Did not access Couchpotato results.'
        assert len(task._all_entries) == 31, 'Did not produce 31 entries'
        for entry in task._all_entries:
            assert entry['quality_req'] == '', (
                'Quality for entry {} should be empty, instead its {}'.format(
                    entry['title'], entry['quality_req']
                )
            )


class TestCouchpotatoWithQuality:
    expected_qualities = {
        'American Ultra': ['720p', '1080p'],
        'Anomalisa': ['720p', '1080p'],
        'Ant-Man': ['720p'],
        'Austin Powers 4': ['720p'],
        'Black Mass': ['720p'],
        'Bridge of Spies': ['720p'],
        'Chronic-Con, Episode 420: A New Dope': ['720p'],
        'Citizenfour': ['720p'],
        'Crimson Peak': ['720p'],
        'Deadpool': ['1080p'],
        'Doug Benson: Doug Dynasty': ['720p'],
        'Ghostbusters': ['720p'],
        'The Gift': ['720p', '1080p', 'dvdrip', 'bluray'],
        'Hail, Caesar!': ['720p'],
        'I Am Chris Farley': ['720p', '1080p'],
        'Inside Out': ['720p'],
        'The Last Witch Hunter': ['720p'],
        'Legend': ['720p'],
        'The Martian': ['1080p'],
        'Minions': ['720p'],
        'A Most Violent Year': ['720p'],
        'Mr. Holmes': ['720p'],
        "Pee-wee's Big Holiday": ['720p'],
        'Sicario': ['720p'],
        'SPECTRE': ['1080p'],
        'Straight Outta Compton': ['720p'],
        'Ted 2': ['720p'],
        'Tomorrowland': ['720p'],
        'Trainwreck': ['720p'],
        'True Story': ['720p'],
        'Untitled Next Bourne Chapter': ['720p'],
    }
    config = """
        tasks:
          couch:
            couchpotato_list:
              base_url: 'http://test.url.com'
              port: 5050
              api_key: '123abc'
              include_data: yes
        """

    def quality_assertion(self, entry):
        assert entry['title'] in self.expected_qualities, (
            f'Could not find entry {entry} in qualities list.'
        )
        expected_quality = self.expected_qualities[entry['title']]

        # Must do this as the order is not guaranteed
        entry_quality = entry['quality_req'].replace(' ', '|').split('|')

        assert len(expected_quality) == len(entry_quality)

        assert all(q in expected_quality for q in entry_quality), (
            'Expected Quality for entry {} should be {}, instead its {}'.format(
                entry['title'], expected_quality, entry.store['quality_req']
            )
        )

    @mock.patch('flexget.components.managed_lists.lists.couchpotato_list.CouchPotatoBase.get_json')
    def test_couchpotato_with_quality(self, mock_get, execute_task):
        mock_get.side_effect = [movie_list_response, qualities_response]
        task = execute_task('couch')

        assert mock_get.call_count == 2

        for entry in task._all_entries:
            self.quality_assertion(entry)
