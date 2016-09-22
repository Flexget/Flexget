from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest
from datetime import datetime, timedelta

from flexget.api.app import base_message
from flexget.api.plugins.series import ObjectsContainer as OC
from flexget.api.plugins.tvdb_lookup import ObjectsContainer as tvdb
from flexget.api.plugins.tvmaze_lookup import ObjectsContainer as tvmaze
from flexget.manager import Session
from flexget.plugins.filter.series import Series, SeriesTask, Episode, Release, AlternateNames
from flexget.utils import json


class TestSeriesRootAPI(object):
    config = """
        tasks: {}
    """

    def test_series_root_get(self, api_client, schema_match):
        # No params
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert data['shows'] == []

        with Session() as session:
            series = Series()
            series.name = 'test series'
            session.add(series)
            session.commit()
            task = SeriesTask('test task')
            series.in_tasks = [task]
            session.commit()

        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        show = data['shows'][0]
        errors = schema_match(OC.single_series_object, show)
        assert not errors

        assert show['series_name'] == 'test series'

    def test_series_configured_param(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series'
            session.add(series)
            session.commit()

        # Default is configured series, no results
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert data['shows'] == []

        # Get unconfigured series
        rsp = api_client.get('/series/?in_config=unconfigured')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        show = data['shows'][0]
        errors = schema_match(OC.single_series_object, show)
        assert not errors

        assert len(data['shows']) == 1
        assert show['series_name'] == 'test series'

        # Add a configured series
        with Session() as session:
            series = Series()
            series.name = 'test series 2'
            session.add(series)
            session.commit()
            task = SeriesTask('test task')
            series.in_tasks = [task]
            session.commit()

        # Get only configures series
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        show = data['shows'][0]
        errors = schema_match(OC.single_series_object, show)
        assert not errors

        assert len(data['shows']) == 1
        assert show['series_name'] == 'test series 2'

        # Get all series
        rsp = api_client.get('/series/?in_config=all')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 2

    def test_series_premieres_param(self, api_client, schema_match):
        # Add a series with an episode of S02E05, not a premiere
        with Session() as session:
            series = Series()
            series.name = 'test series'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode = Episode()
            episode.identifier = 'S02E05'
            episode.identified_by = 'ep'
            episode.season = 2
            episode.number = 5
            episode.series_id = series.id
            series.episodes.append(episode)

            release = Release()
            release.title = 'test release'
            release.downloaded = True

            episode.releases = [release]
            session.commit()

        # Default all, not just premieres
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 1

        # Get only premieres
        rsp = api_client.get('/series/?premieres=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 0

        # Add a premiere episode to another series
        with Session() as session:
            series = Series()
            series.name = 'test series 2'
            session.add(series)

            task = SeriesTask('test task 2')
            series.in_tasks = [task]

            episode = Episode()
            episode.identifier = 'S01E01'
            episode.identified_by = 'ep'
            episode.season = 1
            episode.number = 1
            series.episodes.append(episode)

            release = Release()
            release.title = 'test release 2'
            release.downloaded = True
            episode.releases = [release]
            session.commit()

        # Get only just premieres
        rsp = api_client.get('/series/?premieres=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 1

    def test_series_status_param(self, api_client, schema_match):
        # Add an episode with a release created now
        with Session() as session:
            series = Series()
            series.name = 'test series'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode = Episode()
            episode.identifier = 'S02E05'
            episode.identified_by = 'ep'
            episode.season = 2
            episode.number = 5
            episode.series_id = series.id
            series.episodes.append(episode)

            release = Release()
            release.title = 'test release'
            release.downloaded = True

            episode.releases = [release]
            session.commit()

        # Add an episode with a release created 8 days ago
        with Session() as session:
            series = Series()
            series.name = 'test series 2'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode = Episode()
            episode.identifier = 'S01E01'
            episode.identified_by = 'ep'
            episode.season = 1
            episode.number = 1
            episode.series_id = series.id
            series.episodes.append(episode)

            release = Release()
            release.title = 'test release 2'
            release.downloaded = True
            release.first_seen = datetime.now() - timedelta(days=8)

            episode.releases = [release]
            session.commit()

        # Default all, not just status = new
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 2

        # Just new
        rsp = api_client.get('/series/?status=new')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 1

        # New with days param
        rsp = api_client.get('/series/?status=new&days=9')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 2

        # Just stale
        rsp = api_client.get('/series/?status=stale')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 0

        # Add an episode with a release created over a year ago
        with Session() as session:
            series = Series()
            series.name = 'test series 3'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode = Episode()
            episode.identifier = 'S01E01'
            episode.identified_by = 'ep'
            episode.season = 1
            episode.number = 1
            episode.series_id = series.id
            series.episodes.append(episode)

            release = Release()
            release.title = 'test release 3'
            release.downloaded = True
            release.first_seen = datetime.now() - timedelta(days=366)

            episode.releases = [release]
            session.commit()

        # Just stale
        rsp = api_client.get('/series/?status=stale')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 1

    @pytest.mark.online
    def test_series_lookup_param(self, api_client, schema_match):
        # Add two real shows
        with Session() as session:
            series = Series()
            series.name = 'Suits'
            session.add(series)

            series2 = Series()
            series2.name = 'Stranger Things'
            session.add(series2)

            session.commit()

        rsp = api_client.get('/series/?in_config=all&lookup=tvdb&lookup=tvmaze')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 2

        for show in data['shows']:
            tvdb_lookup = show['lookup']['tvdb']
            assert tvdb_lookup
            errors = schema_match(tvdb.tvdb_series_object, tvdb_lookup)
            assert not errors

            tvmaze_lookup = show['lookup']['tvmaze']
            assert tvmaze_lookup
            errors = schema_match(tvmaze.tvmaze_series_object, tvmaze_lookup)
            assert not errors

    def test_series_post(self, api_client, schema_match):
        payload = {'series_name': 'test series'}

        # Minimal payload
        rsp = api_client.json_post('/series/', data=json.dumps(payload))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.single_series_object, data)
        assert not errors

        # Try to add again
        rsp = api_client.json_post('/series/', data=json.dumps(payload))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload2 = {'series_name': 'test series 2',
                    'begin_episode': 'bla'}

        # Invalid begin episode
        rsp = api_client.json_post('/series/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload3 = {'series_name': 'test series 2',
                    'begin_episode': 's01e01',
                    'alternate_names': [
                        'show1', 'show2'
                    ]}

        # Maximal payload
        rsp = api_client.json_post('/series/', data=json.dumps(payload3))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.single_series_object, data)
        assert not errors

        assert data['series_name'] == payload3['series_name']
        assert data['alternate_names'] == payload3['alternate_names']
        assert data['begin_episode']['identifier'].lower() == payload3['begin_episode']

        payload4 = {'series_name': 'test series 3',
                    'alternate_names': ['show1']}

        # Alternate name already added to different show
        rsp = api_client.json_post('/series/', data=json.dumps(payload4))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesSearchAPI(object):
    config = """
        tasks: {}
    """

    def test_series_search(self, api_client, schema_match):
        with Session() as session:
            series1 = Series()
            series1.name = 'test series1'
            session.add(series1)

            series2 = Series()
            series2.name = 'test series2'
            session.add(series2)

            session.commit()

        rsp = api_client.get('/series/search/test/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_search_object, data)
        assert not errors

        assert len(data['shows']) == 2

        rsp = api_client.get('/series/search/series1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_search_object, data)
        assert not errors

        assert len(data['shows']) == 1

        rsp = api_client.get('/series/search/bla/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_search_object, data)
        assert not errors

        assert len(data['shows']) == 0


class TestSeriesSingleAPI(object):
    config = """
        tasks: {}
    """

    def test_series_get(self, api_client, schema_match):
        with Session() as session:
            series1 = Series()
            series1.name = 'test series1'
            session.add(series1)

            session.commit()

        rsp = api_client.get('/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.single_series_object, data)
        assert not errors

        assert data['series_name'] == 'test series1'

        # No existing ID
        rsp = api_client.get('/series/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_series_delete(self, api_client, schema_match):
        with Session() as session:
            series1 = Series()
            series1.name = 'test series1'
            session.add(series1)

            session.commit()

        rsp = api_client.delete('/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Delete again, no existing ID
        rsp = api_client.delete('/series/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_series_put(self, api_client, schema_match):
        with Session() as session:
            series1 = Series()
            series1.name = 'test series1'
            session.add(series1)

            session.commit()

        payload = {}

        # Validation error
        rsp = api_client.json_put('/series/1/', data=json.dumps(payload))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload1 = {'begin_episode': 's01e01',
                    'alternate_names': ['show1']}

        rsp = api_client.json_put('/series/1/', data=json.dumps(payload1))
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.single_series_object, data)
        assert not errors

        assert data['begin_episode']['identifier'].lower() == payload1['begin_episode']
        assert data['alternate_names'] == payload1['alternate_names']

        with Session() as session:
            series = Series()
            series.name = 'test series2'
            session.add(series)

            alt = AlternateNames('show2')
            series.alternate_names = [alt]
            session.commit()

        payload2 = {'alternate_names': ['show2']}

        # Alternate name used by another show
        rsp = api_client.json_put('/series/1/', data=json.dumps(payload2))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesEpisodesAPI(object):
    config = """
        tasks: {}
    """

    def test_episodes_get(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            episode2 = Episode()
            episode2.identifier = 'S01E01'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 1
            episode2.series_id = series.id

            release = Release()
            release.title = 'test release'
            release.downloaded = True

            episode1.releases = [release]

            series.episodes.append(episode1)
            series.episodes.append(episode2)
            session.commit()

        # No series
        rsp = api_client.get('/series/10/episodes/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_list_schema, data)
        assert not errors

        assert len(data['episodes']) == data['number_of_episodes'] == 2

        # Delete all episodes
        rsp = api_client.delete('/series/1/episodes/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_list_schema, data)
        assert not errors

        assert len(data['episodes']) == data['number_of_episodes'] == 0


class TestSeriesEpisodeAPI(object):
    config = """
        tasks: {}
    """

    def test_episode_get(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            episode2 = Episode()
            episode2.identifier = 'S01E01'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 1
            episode2.series_id = series.id

            release = Release()
            release.title = 'test release'
            release.downloaded = True

            episode1.releases = [release]

            series.episodes.append(episode1)
            series.episodes.append(episode2)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            session.commit()

        rsp = api_client.get('/series/1/episodes/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_schema, data)
        assert not errors

        assert data['episode']['identifier'] == 'S01E01'
        assert data['episode']['identified_by'] == 'ep'
        assert data['episode']['season'] == 1
        assert data['episode']['number'] == 1
        assert data['episode']['premiere_type'] == 'Series Premiere'

        # No series ID
        rsp = api_client.get('/series/10/episodes/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode ID
        rsp = api_client.get('/series/1/episodes/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.get('/series/2/episodes/1/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Delete
        rsp = api_client.delete('/series/1/episodes/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

class TestSeriesReleasesAPI(object):
    config = """
        tasks: {}
    """

    def test_releases_get(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            release1 = Release()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = Release()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            episode1.releases = [release1, release2]
            series.episodes.append(episode1)

            session.commit()

        rsp = api_client.get('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.release_list_schema, data)
        assert not errors

        assert len(data['releases']) == data['number_of_releases'] == 2

        # Just downloaded releases
        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.release_list_schema, data)
        assert not errors

        assert len(data['releases']) == data['number_of_releases'] == 1
        assert data['releases'][0]['title'] == 'downloaded release'

        # Just un-downloaded releases
        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.release_list_schema, data)
        assert not errors

        assert len(data['releases']) == data['number_of_releases'] == 1
        assert data['releases'][0]['title'] == 'un-downloaded release'