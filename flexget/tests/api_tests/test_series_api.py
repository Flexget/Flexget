from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.api.app import base_message
from flexget.components.series.api import ObjectsContainer as OC
from flexget.components.thetvdb.api import ObjectsContainer as tvdb
from flexget.components.tvmaze.api import ObjectsContainer as tvmaze
from flexget.components.seen.db import SeenEntry
from flexget.manager import Session

# TODO: would be nicer to import db module
from flexget.components.series.db import (
    Series,
    SeriesTask,
    Episode,
    EpisodeRelease,
    AlternateNames,
    Season,
    SeasonRelease,
)
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

        assert data == []

        with Session() as session:
            series = Series()
            series.name = 'test series'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        show = data[0]
        errors = schema_match(OC.single_series_object, show)
        assert not errors

        assert show['name'] == 'test series'

    def test_series_configured_param(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series'
            session.add(series)

        # Default is configured series, no results
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert data == []

        # Get unconfigured series
        rsp = api_client.get('/series/?in_config=unconfigured')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        show = data[0]
        errors = schema_match(OC.single_series_object, show)
        assert not errors

        assert len(data) == 1
        assert show['name'] == 'test series'

        # Add a configured series
        with Session() as session:
            series = Series()
            series.name = 'test series 2'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

        # Get only configures series
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        show = data[0]
        errors = schema_match(OC.single_series_object, show)
        assert not errors

        assert len(data) == 1
        assert show['name'] == 'test series 2'

        # Get all series
        rsp = api_client.get('/series/?in_config=all')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 2

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

            release = EpisodeRelease()
            release.title = 'test release'
            release.downloaded = True

            episode.releases = [release]

        # Default all, not just premieres
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 1

        # Get only premieres
        rsp = api_client.get('/series/?premieres=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 0

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

            release = EpisodeRelease()
            release.title = 'test release 2'
            release.downloaded = True
            episode.releases = [release]

        # Get only just premieres
        rsp = api_client.get('/series/?premieres=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 1

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

        rsp = api_client.get('/series/?in_config=all&lookup=tvdb&lookup=tvmaze')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 2

        for show in data:
            tvdb_lookup = show['lookup']['tvdb']
            assert tvdb_lookup
            errors = schema_match(tvdb.tvdb_series_object, tvdb_lookup)
            assert not errors

            tvmaze_lookup = show['lookup']['tvmaze']
            assert tvmaze_lookup
            errors = schema_match(tvmaze.tvmaze_series_object, tvmaze_lookup)
            assert not errors

    def test_series_post(self, api_client, schema_match):
        payload = {'name': 'test series'}

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

        payload2 = {'name': 'test series 2', 'begin_episode': 'bla'}

        # Invalid begin episode
        rsp = api_client.json_post('/series/', data=json.dumps(payload2))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload3 = {
            'name': 'test series 2',
            'begin_episode': 's01e01',
            'alternate_names': ['show1', 'show2'],
        }

        # Maximal payload
        rsp = api_client.json_post('/series/', data=json.dumps(payload3))
        assert rsp.status_code == 201, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.single_series_object, data)
        assert not errors

        assert data['name'] == payload3['name']
        assert data['alternate_names'] == payload3['alternate_names']
        assert data['begin_episode']['identifier'].lower() == payload3['begin_episode']

        payload4 = {'name': 'test series 3', 'alternate_names': ['show1']}

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

        rsp = api_client.get('/series/search/test/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 2

        rsp = api_client.get('/series/search/series1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 1

        rsp = api_client.get('/series/search/bla/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 0


class TestSeriesSingleAPI(object):
    config = """
        tasks: {}
    """

    def test_series_get(self, api_client, schema_match):
        with Session() as session:
            series1 = Series()
            series1.name = 'test series1'
            session.add(series1)

        rsp = api_client.get('/series/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.single_series_object, data)
        assert not errors

        assert data['name'] == 'test series1'

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

        payload = {}

        # Validation error
        rsp = api_client.json_put('/series/1/', data=json.dumps(payload))
        assert rsp.status_code == 422, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        payload1 = {'begin_episode': 's01e01', 'alternate_names': ['show1']}

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

        payload2 = {'alternate_names': ['show2']}

        # Alternate name used by another show
        rsp = api_client.json_put('/series/1/', data=json.dumps(payload2))
        assert rsp.status_code == 409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Non existent show
        rsp = api_client.json_put('/series/10/', data=json.dumps(payload2))
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesSeasonsAPI(object):
    config = """
        tasks: {}
    """

    def test_seasons_get(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            season1 = Season()
            season1.identifier = 'S01'
            season1.identified_by = 'ep'
            season1.season = 1
            season1.series_id = series.id

            season2 = Season()
            season2.identifier = 'S02'
            season2.identified_by = 'ep'
            season2.season = 2
            season2.series_id = series.id

            release = SeasonRelease()
            release.title = 'test release'
            release.downloaded = True

            season1.releases = [release]

            series.seasons.append(season1)
            series.seasons.append(season2)

        # No series
        rsp = api_client.get('/series/10/seasons/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/seasons/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seasons_list_schema, data)
        assert not errors

        assert len(data) == 2

        # Delete all episodes
        rsp = api_client.delete('/series/1/seasons/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/seasons/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.seasons_list_schema, data)
        assert not errors

        assert len(data) == 0


class TestSeriesSeasonAPI(object):
    config = """
        tasks: {}
    """

    def test_season(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            task = SeriesTask('test task')
            series.in_tasks = [task]

            season1 = Season()
            season1.identifier = 'S01'
            season1.identified_by = 'ep'
            season1.season = 1
            season1.series_id = series.id

            season2 = Season()
            season2.identifier = 'S02'
            season2.identified_by = 'ep'
            season2.season = 2
            season2.series_id = series.id

            release = SeasonRelease()
            release.title = 'test release'
            release.downloaded = True

            season1.releases = [release]

            series.seasons.append(season1)
            series.seasons.append(season2)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

        rsp = api_client.get('/series/1/seasons/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_object, data)
        assert not errors

        assert data['identifier'] == 'S01'
        assert data['identified_by'] == 'ep'
        assert data['season'] == 1

        # No series ID
        rsp = api_client.get('/series/10/seasons/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No season ID
        rsp = api_client.get('/series/1/seasons/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # season does not belong to series
        rsp = api_client.get('/series/2/seasons/1/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Delete
        rsp = api_client.delete('/series/1/seasons/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/seasons/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/series/1/seasons/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/series/10/seasons/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesSeasonReleasesAPI(object):
    config = """
        tasks: {}
    """

    def create_data(self):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            season1 = Season()
            season1.identifier = 'S01'
            season1.identified_by = 'ep'
            season1.season = 1
            season1.series_id = series.id

            release1 = SeasonRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = SeasonRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            season1.releases = [release1, release2]
            series.seasons.append(season1)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            season2 = Season()
            season2.identifier = 'S02'
            season2.identified_by = 'ep'
            season2.season = 2
            season2.series_id = series2.id

            series2.seasons.append(season2)

    def test_season_releases_get(self, api_client, schema_match):
        self.create_data()

        rsp = api_client.get('/series/1/seasons/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 2

        # Just downloaded releases
        rsp = api_client.get('/series/1/seasons/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 1
        assert data[0]['title'] == 'downloaded release'

        # Just un-downloaded releases
        rsp = api_client.get('/series/1/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 1
        assert data[0]['title'] == 'un-downloaded release'

        # No series
        rsp = api_client.get('/series/10/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.get('/series/1/seasons/10/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.get('/series/2/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_releases_delete(self, api_client, schema_match):
        self.create_data()

        rsp = api_client.delete('/series/1/seasons/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/seasons/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 1
        assert data[0]['title'] == 'un-downloaded release'

        rsp = api_client.delete('/series/1/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/seasons/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 0

        # No series
        rsp = api_client.delete('/series/10/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.delete('/series/1/seasons/10/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.delete('/series/2/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_releases_put(self, api_client, schema_match):
        self.create_data()

        rsp = api_client.json_put('/series/1/seasons/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/seasons/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 0

        rsp = api_client.get('/series/1/seasons/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.season_release_list_schema, data)
        assert not errors

        assert len(data) == 2

        # No series
        rsp = api_client.json_put('/series/10/seasons/1/releases/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.json_put('/series/1/seasons/10/releases/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.json_put('/series/2/seasons/1/releases/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
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

            release = EpisodeRelease()
            release.title = 'test release'
            release.downloaded = True

            episode1.releases = [release]

            series.episodes.append(episode1)
            series.episodes.append(episode2)

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

        assert len(data) == 2

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

        assert len(data) == 0


class TestSeriesEpisodeAPI(object):
    config = """
        tasks: {}
    """

    def test_episode(self, api_client, schema_match):
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

            release = EpisodeRelease()
            release.title = 'test release'
            release.downloaded = True

            episode1.releases = [release]

            series.episodes.append(episode1)
            series.episodes.append(episode2)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

        rsp = api_client.get('/series/1/episodes/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_object, data)
        assert not errors

        assert data['identifier'] == 'S01E01'
        assert data['identified_by'] == 'ep'
        assert data['season'] == 1
        assert data['number'] == 1
        assert data['premiere'] == 'Series Premiere'

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

        # Episode does not belong to series
        rsp = api_client.delete('/series/2/episodes/1/')
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

        rsp = api_client.delete('/series/1/episodes/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/series/10/episodes/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesEpisodeReleasesAPI(object):
    config = """
        tasks: {}
    """

    def test_releases_get(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            release1 = EpisodeRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = EpisodeRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            episode1.releases = [release1, release2]
            series.episodes.append(episode1)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series2.id

            series2.episodes.append(episode2)

        rsp = api_client.get('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 2

        # Just downloaded releases
        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 1
        assert data[0]['title'] == 'downloaded release'

        # Just un-downloaded releases
        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 1
        assert data[0]['title'] == 'un-downloaded release'

        # No series
        rsp = api_client.get('/series/10/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.get('/series/1/episodes/10/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.get('/series/2/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_releases_delete(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            release1 = EpisodeRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = EpisodeRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            episode1.releases = [release1, release2]
            series.episodes.append(episode1)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series2.id

            series2.episodes.append(episode2)

        rsp = api_client.delete('/series/1/episodes/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 1
        assert data[0]['title'] == 'un-downloaded release'

        rsp = api_client.delete('/series/1/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 0

        # No series
        rsp = api_client.delete('/series/10/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.delete('/series/1/episodes/10/releases/?downloaded=false')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.delete('/series/2/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_releases_put(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            release1 = EpisodeRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = EpisodeRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            episode1.releases = [release1, release2]
            series.episodes.append(episode1)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series2.id

            series2.episodes.append(episode2)

        rsp = api_client.json_put('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 0

        rsp = api_client.get('/series/1/episodes/1/releases/?downloaded=false')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_list_schema, data)
        assert not errors

        assert len(data) == 2

        # No series
        rsp = api_client.json_put('/series/10/episodes/1/releases/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.json_put('/series/1/episodes/10/releases/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.json_put('/series/2/episodes/1/releases/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesEpisodeReleaseAPI(object):
    config = """
        tasks: {}
    """

    def test_release_get(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series.id

            release1 = EpisodeRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = EpisodeRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            release3 = EpisodeRelease()
            release3.title = 'downloaded release'
            release3.downloaded = True

            episode1.releases = [release1, release2]
            episode2.releases = [release3]
            series.episodes.append(episode1)
            series.episodes.append(episode2)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series2.id

            series2.episodes.append(episode2)

        rsp = api_client.get('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_object, data)
        assert not errors

        assert data['downloaded'] is True
        assert data['title'] == 'downloaded release'

        rsp = api_client.get('/series/1/episodes/1/releases/2/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_object, data)
        assert not errors

        assert data['downloaded'] is False
        assert data['title'] == 'un-downloaded release'

        # No series
        rsp = api_client.get('/series/10/episodes/1/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.get('/series/1/episodes/10/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.get('/series/2/episodes/1/releases/1/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No release
        rsp = api_client.get('/series/1/episodes/1/releases/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Release does not belong to episode
        rsp = api_client.get('/series/1/episodes/1/releases/3/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_release_put(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series.id

            release1 = EpisodeRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = EpisodeRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            release3 = EpisodeRelease()
            release3.title = 'downloaded release'
            release3.downloaded = True

            episode1.releases = [release1, release2]
            episode2.releases = [release3]
            series.episodes.append(episode1)
            series.episodes.append(episode2)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series2.id

            series2.episodes.append(episode2)

        # No series
        rsp = api_client.json_put('/series/10/episodes/1/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.json_put('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_object, data)
        assert not errors

        # Cannot reset if already downloaded
        rsp = api_client.json_put('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.json_put('/series/1/episodes/10/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.json_put('/series/2/episodes/1/releases/1/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No release
        rsp = api_client.json_put('/series/1/episodes/1/releases/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Release does not belong to episode
        rsp = api_client.json_put('/series/1/episodes/1/releases/3/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

    def test_release_delete(self, api_client, schema_match):
        with Session() as session:
            series = Series()
            series.name = 'test series 1'
            session.add(series)

            episode1 = Episode()
            episode1.identifier = 'S01E01'
            episode1.identified_by = 'ep'
            episode1.season = 1
            episode1.number = 1
            episode1.series_id = series.id

            episode2 = Episode()
            episode2.identifier = 'S01E02'
            episode2.identified_by = 'ep'
            episode2.season = 1
            episode2.number = 2
            episode2.series_id = series.id

            release1 = EpisodeRelease()
            release1.title = 'downloaded release'
            release1.downloaded = True

            release2 = EpisodeRelease()
            release2.title = 'un-downloaded release'
            release2.downloaded = False

            release3 = EpisodeRelease()
            release3.title = 'downloaded release'
            release3.downloaded = True

            episode1.releases = [release1, release2]
            episode2.releases = [release3]
            series.episodes.append(episode1)
            series.episodes.append(episode2)

            series2 = Series()
            series2.name = 'test series 2'
            session.add(series2)

            episode3 = Episode()
            episode3.identifier = 'S01E02'
            episode3.identified_by = 'ep'
            episode3.season = 1
            episode3.number = 2
            episode3.series_id = series2.id

            release4 = EpisodeRelease()
            release4.title = 'downloaded release'
            release4.downloaded = True

            episode3.releases = [release4]

            series2.episodes.append(episode3)

        # No series
        rsp = api_client.delete('/series/10/episodes/1/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No episode for series
        rsp = api_client.delete('/series/1/episodes/10/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Episode does not belong to series
        rsp = api_client.delete('/series/2/episodes/1/releases/1/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # No release
        rsp = api_client.delete('/series/1/episodes/1/releases/10/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Release does not belong to episode
        rsp = api_client.delete('/series/1/episodes/1/releases/3/')
        assert rsp.status_code == 400, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.delete('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Already deleted
        rsp = api_client.delete('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors


class TestSeriesForgetFlag(object):
    config = """
            tasks:
              series_data:
                mock:
                  - {title: 'series.foo.s01e01.720p.hdtv-flexget'}
                  - {title: 'series.foo.s01e01.1080p.hdtv-flexget'}
                  - {title: 'series.foo.s01e02.720p.hdtv-flexget'}
                  - {title: 'series.foo.s01e02.1080p.hdtv-flexget'}
                series:
                  - series foo:
                      qualities:
                        - 720p
                        - 1080p

    """

    def test_delete_series_with_forget_flag(self, execute_task, api_client, schema_match):
        task = execute_task('series_data')
        assert len(task.accepted) == 4

        # Get series
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 1

        # Get seen object
        with Session() as session:
            seen = session.query(SeenEntry).all()
            assert len(seen) == 4

        # Delete with forget flag
        rsp = api_client.delete('/series/1/?forget=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Get series
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data) == 0

        # Get seen object
        with Session() as session:
            seen = session.query(SeenEntry).all()
            assert len(seen) == 0

    def test_delete_series_episode_with_forget_flag(self, execute_task, api_client, schema_match):
        task = execute_task('series_data')
        assert len(task.accepted) == 4

        # Get episode 1
        rsp = api_client.get('/series/1/episodes/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_object, data)
        assert not errors

        # Get episode 2
        rsp = api_client.get('/series/1/episodes/2/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_object, data)
        assert not errors

        # Get seen object
        with Session() as session:
            seen = session.query(SeenEntry).all()
            assert len(seen) == 4

        # Delete with forget flag
        rsp = api_client.delete('/series/1/episodes/1/?forget=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Get episode 1
        rsp = api_client.get('/series/1/episodes/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        # Get episode 2
        rsp = api_client.get('/series/1/episodes/2/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_object, data)
        assert not errors

        # Get seen object
        with Session() as session:
            seen = session.query(SeenEntry).all()
            assert len(seen) == 2

    def test_delete_series_release_with_forget_flag(self, execute_task, api_client, schema_match):
        task = execute_task('series_data')
        assert len(task.accepted) == 4

        # Get release 1 for episode 1
        rsp = api_client.get('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.episode_release_object, data)
        assert not errors

        # Get seen object
        with Session() as session:
            seen = session.query(SeenEntry).all()
            assert len(seen) == 4

        rsp = api_client.delete('/series/1/episodes/1/releases/1/?forget=true')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        rsp = api_client.get('/series/1/episodes/1/releases/1/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors

        with Session() as session:
            seen = session.query(SeenEntry).all()
            assert len(seen) == 3


class TestSeriesPagination(object):
    config = 'tasks: {}'

    def test_series_pagination(self, api_client, link_headers):
        number_of_series = 200
        with Session() as session:
            for i in range(number_of_series):
                series = Series()
                session.add(series)

                series.name = 'test series {}'.format(i)
                task = SeriesTask('test task')
                series.in_tasks = [task]

        # Default values
        rsp = api_client.get('/series/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/series/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('series/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_episodes_pagination(self, api_client, link_headers):
        number_of_episodes = 200
        with Session() as session:
            series = Series()
            session.add(series)

            series.name = 'test series'
            task = SeriesTask('test task')
            series.in_tasks = [task]

            for i in range(number_of_episodes):
                episode = Episode()
                episode.identifier = 'S01E0{}'.format(i)
                episode.identified_by = 'ep'
                episode.season = 1
                episode.number = i
                episode.series_id = series.id
                series.episodes.append(episode)

        # Default values
        rsp = api_client.get('/series/1/episodes/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50
        assert int(rsp.headers['Series-ID']) == 1

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/series/1/episodes/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100
        assert int(rsp.headers['Series-ID']) == 1

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('series/1/episodes/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50
        assert int(rsp.headers['Series-ID']) == 1

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1

    def test_releases_pagination(self, api_client, link_headers):
        number_of_releases = 200
        with Session() as session:
            series = Series()
            session.add(series)

            series.name = 'test series'
            task = SeriesTask('test task')
            series.in_tasks = [task]

            episode = Episode()
            episode.identifier = 'S01E01'
            episode.identified_by = 'ep'
            episode.season = 1
            episode.number = 1
            episode.series_id = series.id
            series.episodes.append(episode)

            for i in range(number_of_releases):
                release = EpisodeRelease()
                release.title = 'test release {}'.format(i)
                release.downloaded = True

                episode.releases.append(release)

        # Default values
        rsp = api_client.get('/series/1/episodes/1/releases/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50  # Default page size
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50
        assert int(rsp.headers['Series-ID']) == 1
        assert int(rsp.headers['Episode-ID']) == 1

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 2

        # Change page size
        rsp = api_client.get('/series/1/episodes/1/releases/?per_page=100')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 100
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 100
        assert int(rsp.headers['Series-ID']) == 1
        assert int(rsp.headers['Episode-ID']) == 1

        links = link_headers(rsp)
        assert links['last']['page'] == 2
        assert links['next']['page'] == 2

        # Get different page
        rsp = api_client.get('series/1/episodes/1/releases/?page=2')
        assert rsp.status_code == 200
        data = json.loads(rsp.get_data(as_text=True))

        assert len(data) == 50
        assert int(rsp.headers['total-count']) == 200
        assert int(rsp.headers['count']) == 50
        assert int(rsp.headers['Series-ID']) == 1
        assert int(rsp.headers['Episode-ID']) == 1

        links = link_headers(rsp)
        assert links['last']['page'] == 4
        assert links['next']['page'] == 3
        assert links['prev']['page'] == 1
