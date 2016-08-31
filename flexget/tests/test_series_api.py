from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from mock import patch

from flexget.manager import Session
from flexget.plugins.filter import series
from flexget.utils import json


class TestSeriesAPI(object):
    config = """
        tasks: {}
    """

    @patch.object(series, 'get_series_summary')
    def test_series_list_get(self, mock_series_list, api_client):
        def search(*args, **kwargs):
            if 'count' in kwargs:
                return 0
            else:
                with Session() as session:
                    return session.query(series.Series)

        mock_series_list.side_effect = search

        # No params
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Default params
        rsp = api_client.get('/series/?max=100&sort_by=show_name&in_config=configured&order=desc&page=1')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Changed params
        rsp = api_client.get('/series/?status=new&max=10&days=4&sort_by=last_download_date&in_config=all'
                             '&premieres=true&order=asc&page=2')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        # Negative test, invalid parameter
        rsp = api_client.get('/series/?status=bla&max=10&days=4&sort_by=last_download_date&in_config=all'
                             '&premieres=true&order=asc&page=2')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        assert mock_series_list.call_count == 6, 'Should have 3 calls, is actually %s' % mock_series_list.call_count

    @patch.object(series, 'new_eps_after')
    @patch.object(series, 'get_latest_release')
    @patch.object(series, 'shows_by_name')
    def test_series_search(self, mocked_series_search, mock_latest_release, mock_new_eps_after, api_client):
        show = series.Series()
        episode = series.Episode()
        release = series.Release()
        release.downloaded = True
        episode.releases.append(release)

        mock_latest_release.return_value = episode
        mock_new_eps_after.return_value = 0
        mocked_series_search.return_value = [show]

        rsp = api_client.get('/series/search/the%20big%20bang%20theory/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_latest_release.called
        assert mock_new_eps_after.called
        assert mocked_series_search.called

    @patch.object(series, 'new_eps_after')
    @patch.object(series, 'get_latest_release')
    @patch.object(series, 'show_by_id')
    def test_series_get(self, mock_show_by_id, mock_latest_release, mock_new_eps_after, api_client):
        show = series.Series()
        episode = series.Episode()
        release = series.Release()
        release.downloaded = True
        episode.releases.append(release)

        mock_show_by_id.return_value = show
        mock_latest_release.return_value = episode
        mock_new_eps_after.return_value = 0

        rsp = api_client.get('/series/1/')

        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_latest_release.called
        assert mock_new_eps_after.called
        assert mock_show_by_id.called

    @patch.object(series, 'remove_series')
    @patch.object(series, 'show_by_id')
    def test_series_delete(self, mock_show_by_id, mock_forget_series, api_client):
        show = series.Series()
        show.name = 'Some name'

        mock_show_by_id.return_value = show

        rsp = api_client.delete('/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called
        assert mock_forget_series.called

    @patch.object(series, 'new_eps_after')
    @patch.object(series, 'get_latest_release')
    @patch.object(series, 'set_series_begin')
    @patch.object(series, 'show_by_id')
    def test_series_begin(self, mock_show_by_id, mock_series_begin, mock_latest_release, mock_new_eps_after,
                          api_client):
        show = series.Series()
        episode = series.Episode()
        release = series.Release()
        release.downloaded = True
        episode.releases.append(release)
        ep_id = {"episode_identifier": "s01e01"}

        mock_show_by_id.return_value = show
        mock_latest_release.return_value = episode
        mock_new_eps_after.return_value = 0

        rsp = api_client.json_put('/series/1/', data=json.dumps(ep_id))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called

    def test_new_series_begin(self, execute_task, api_client):
        show = 'Test Show'
        new_show = {
            "series_name": show,
            "episode_identifier": "s01e01",
            "alternate_names": ['show1', 'show2']
        }

        rsp = api_client.json_post(('/series/'), data=json.dumps(new_show))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    @patch.object(series, 'show_by_id')
    def test_series_get_episodes(self, mock_show_by_id, api_client):
        show = series.Series()
        episode = series.Episode()
        release = series.Release()
        release.downloaded = True
        episode.releases.append(release)
        show.episodes.append(episode)

        mock_show_by_id.return_value = show

        rsp = api_client.get('/series/1/episodes/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called

    def test_series_delete_episodes(self, api_client):
        show = 'Test Show'
        new_show = {
            "series_name": show,
            "episode_identifier": "s01e01",
            "alternate_names": ['show1', 'show2']
        }

        rsp = api_client.json_post(('/series/'), data=json.dumps(new_show))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.delete('/series/1/episodes/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

    @patch.object(series, 'episode_in_show')
    @patch.object(series, 'episode_by_id')
    @patch.object(series, 'show_by_id')
    def test_series_get_episode(self, mock_show_by_id, mock_episode_by_id, mock_episode_in_show, api_client):
        show = series.Series()
        episode = series.Episode()

        mock_show_by_id.return_value = show
        mock_episode_by_id.return_value = episode

        rsp = api_client.get('/series/1/episodes/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called
        assert mock_episode_by_id.called
        assert mock_episode_in_show.called

    @patch.object(series, 'remove_series_episode')
    @patch.object(series, 'episode_in_show')
    @patch.object(series, 'episode_by_id')
    @patch.object(series, 'show_by_id')
    def test_series_delete_episode(self, mock_show_by_id, mock_episode_by_id, mock_episode_in_show,
                                   mock_remove_series_episode, api_client):
        show = series.Series()
        episode = series.Episode()

        mock_show_by_id.return_value = show
        mock_episode_by_id.return_value = episode

        rsp = api_client.delete('/series/1/episodes/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called
        assert mock_episode_by_id.called
        assert mock_episode_in_show.called
        assert mock_remove_series_episode.called

    @patch.object(series, 'episode_in_show')
    @patch.object(series, 'episode_by_id')
    @patch.object(series, 'show_by_id')
    def test_series_get_episode_releases(self, mock_show_by_id, mock_episode_by_id, mock_episode_in_show, api_client):
        show = series.Series()
        episode = series.Episode()

        mock_show_by_id.return_value = show
        mock_episode_by_id.return_value = episode

        rsp = api_client.get('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert mock_show_by_id.call_count == 3
        assert mock_episode_by_id.call_count == 3
        assert mock_episode_in_show.call_count == 3

    @patch.object(series, 'episode_in_show')
    @patch.object(series, 'episode_by_id')
    @patch.object(series, 'show_by_id')
    def test_series_delete_episode_releases(self, mock_show_by_id, mock_episode_by_id, mock_episode_in_show,
                                            api_client):
        show = series.Series()
        episode = series.Episode()

        mock_show_by_id.return_value = show
        mock_episode_by_id.return_value = episode

        rsp = api_client.delete('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.delete('/series/1/episodes/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        rsp = api_client.delete('/series/1/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        assert mock_show_by_id.call_count == 3
        assert mock_episode_by_id.call_count == 3
        assert mock_episode_in_show.call_count == 3

    @patch.object(series, 'release_in_episode')
    @patch.object(series, 'release_by_id')
    @patch.object(series, 'episode_in_show')
    @patch.object(series, 'episode_by_id')
    @patch.object(series, 'show_by_id')
    def test_series_get_release(self, mock_show_by_id, mock_episode_by_id, mock_episode_in_show, mock_release_by_id,
                                mock_release_in_episode, api_client):
        show = series.Series()
        episode = series.Episode()
        release = series.Release()

        mock_show_by_id.return_value = show
        mock_episode_by_id.return_value = episode
        mock_release_by_id.return_value = release

        rsp = api_client.get('/series/2/episodes/653/releases/1551/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called
        assert mock_episode_by_id.called
        assert mock_episode_in_show.called
        assert mock_release_by_id.called
        assert mock_release_in_episode.called

    @patch.object(series, 'delete_release_by_id')
    @patch.object(series, 'release_in_episode')
    @patch.object(series, 'release_by_id')
    @patch.object(series, 'episode_in_show')
    @patch.object(series, 'episode_by_id')
    @patch.object(series, 'show_by_id')
    def test_series_delete_release(self, mock_show_by_id, mock_episode_by_id, mock_episode_in_show, mock_release_by_id,
                                   mock_release_in_episode, mock_delete_release_by_id, api_client):
        show = series.Series()
        episode = series.Episode()
        release = series.Release()

        mock_show_by_id.return_value = show
        mock_episode_by_id.return_value = episode
        mock_release_by_id.return_value = release

        rsp = api_client.delete('/series/2/episodes/653/releases/1551/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        assert mock_show_by_id.called
        assert mock_episode_by_id.called
        assert mock_episode_in_show.called
        assert mock_release_by_id.called
        assert mock_release_in_episode.called
        assert mock_delete_release_by_id.called
