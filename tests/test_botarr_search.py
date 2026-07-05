from unittest import mock

import pytest
from requests import RequestException

from flexget.plugins.input.botarr_search import BotarrSearch


class TestBotarrSearch:
    config = """
        tasks:
          test_search_input:
            botarr_search:
              url: http://localhost:3001
              query: "Breaking Bad"
              providers: [Nibl, SubsPlease]
              max_results: 1
              
          test_search_input_no_max:
            botarr_search:
              url: http://localhost:3001
              query: "Breaking Bad"
              
          test_search_input_no_query:
            botarr_search:
              url: http://localhost:3001

          test_search_plugin:
            accept_all: yes
            discover:
              release_estimations: ignore
              what:
                - mock:
                    - {"title": "Frieren Beyond Journey's End S01E01"}
              from:
                - botarr_search:
                    url: http://localhost:3001
                    query: "{{title}}"

          test_search_render_error:
            accept_all: yes
            discover:
              release_estimations: ignore
              what:
                - mock:
                    - {title: 'Frieren'}
              from:
                - botarr_search:
                    url: http://localhost:3001
                    query: "{{missing_field}}"

          test_search_http_error:
            botarr_search:
              url: http://localhost:3001
              query: "Breaking Bad"
    """

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_search_input(self, mock_get, execute_task):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {
            'results': [
                {
                    'filename': 'Breaking Bad S01E01.mkv',
                    'server': 'Rizon',
                    'channel': '#channel1',
                    'bot': 'Bot1',
                    'pack_number': 100,
                    'size': 1024,
                },
                {
                    'filename': 'Breaking Bad S01E02.mkv',
                    'url': {'network': 'Rizon', 'channel': '#channel1', 'bot': 'Bot1', 'slot': 101},
                },
                {
                    'url': {'network': 'Rizon'}, # missing filename
                }
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        task = execute_task('test_search_input')
        
        # max_results was 1, so only 1 entry should be produced
        assert len(task.entries) == 1
        entry = task.entries[0]
        assert entry['title'] == 'Breaking Bad S01E01.mkv'
        assert entry['url'] == 'irc://Rizon/#channel1/Bot1/100'
        assert entry['botarr_network'] == 'Rizon'
        assert entry['botarr_channel'] == '#channel1'
        assert entry['botarr_bot'] == 'Bot1'
        assert entry['botarr_slot'] == 100
        assert entry['botarr_size'] == 1024

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == 'http://localhost:3001/api/search'
        assert kwargs['params']['query'] == 'Breaking Bad'
        assert kwargs['params']['providers'] == 'Nibl,SubsPlease'

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_search_input_no_max(self, mock_get, execute_task):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {
            'results': [
                {
                    'filename': 'File.mkv',
                    'server': 'Rizon',
                },
                {
                    'url': {'network': 'Rizon'}, # missing filename
                }
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        task = execute_task('test_search_input_no_max')
        assert len(task.entries) == 1

    def test_botarr_search_input_no_query(self, execute_task):
        with pytest.raises(Exception) as excinfo:
            execute_task('test_search_input_no_query')
        assert '`query` is required' in str(excinfo.value)

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_search_plugin(self, mock_get, execute_task):
        mock_resp = mock.Mock()
        mock_resp.json.return_value = {
            'results': [
                {
                    'filename': "Frieren Beyond Journey's End S01E01.mkv",
                    'url': {'network': 'Rizon', 'channel': '#channel1', 'bot': 'Bot1', 'slot': 101},
                }
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        task = execute_task('test_search_plugin')
        
        # Discover will produce the entry from the search plugin
        assert len(task.entries) == 1
        entry = task.entries[0]
        assert entry['title'] == "Frieren Beyond Journey's End S01E01.mkv"
        
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs['params']['query'] == "Frieren Beyond Journey's End S01E01"

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_search_render_error(self, mock_get, execute_task):
        task = execute_task('test_search_render_error')
        # Render error should mean 0 results are returned and plugin skips gracefully
        assert len(task.entries) == 0
        mock_get.assert_not_called()

    @mock.patch('flexget.utils.requests.Session.get')
    def test_botarr_search_http_error(self, mock_get, execute_task):
        mock_get.side_effect = RequestException('Connection timeout')
        task = execute_task('test_search_http_error')
        # Should catch error and return [] gracefully
        assert len(task.entries) == 0
