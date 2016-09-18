from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget.api.plugins.series import ObjectsContainer as OC
from flexget.manager import Session
from flexget.plugins.filter.series import Series, SeriesTask
from flexget.utils import json


class TestSeriesAPI(object):
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
        errors = schema_match(OC.show_details_schema, show)
        assert not errors

        assert show['show_name'] == 'test series'

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
        errors = schema_match(OC.show_details_schema, show)
        assert not errors

        assert len(data['shows']) == 1
        assert show['show_name'] == 'test series'

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
        errors = schema_match(OC.show_details_schema, show)
        assert not errors

        assert len(data['shows']) == 1
        assert show['show_name'] == 'test series 2'

        # Get all series
        rsp = api_client.get('/series/?in_config=all')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code
        data = json.loads(rsp.get_data(as_text=True))

        errors = schema_match(OC.series_list_schema, data)
        assert not errors

        assert len(data['shows']) == 2
