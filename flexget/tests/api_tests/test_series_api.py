from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest
from datetime import datetime, timedelta

from flexget.api.app import base_message
from flexget.api.plugins.series import ObjectsContainer as OC
from flexget.api.plugins.tvdb_lookup import ObjectsContainer as tvdb
from flexget.api.plugins.tvmaze_lookup import ObjectsContainer as tvmaze
from flexget.manager import Session
from flexget.plugins.filter.series import Series, SeriesTask, Episode, Release
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
        assert rsp.status_code ==409, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(base_message, data)
        assert not errors
