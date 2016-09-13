from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flexget.plugins.filter.series import Series, SeriesTask

from mock import patch

from flexget.manager import Session
from flexget.plugins.filter import series
from flexget.utils import json
from flexget.plugins.api.series import ObjectsContainer as OC


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

        errors = schema_match(OC.show_details_schema, data['shows'][0])
        assert not errors
