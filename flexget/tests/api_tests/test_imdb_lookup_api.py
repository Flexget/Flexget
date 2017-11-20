from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.api.plugins.imdb_lookup import ObjectsContainer as OC
from flexget.utils import json


@pytest.mark.online
class TestIMDBLookupAPI(object):
    config = 'tasks: {}'

    def test_imdb_search(self, api_client, schema_match):
        # No params
        rsp = api_client.get('/imdb/search/')
        assert rsp.status_code == 404, 'Response code is %s' % rsp.status_code

        # Lookup by title
        rsp = api_client.get('/imdb/search/matrix/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_object, data)
        assert not errors
        assert len(data) > 1

        # Lookup by IMDB ID
        rsp = api_client.get('/imdb/search/tt0234215/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_object, data)
        assert not errors

        assert len(data) == 1

        # Lookup non-existing title
        rsp = api_client.get('/imdb/search/sdfgsdfgsdfgsdfg/')
        assert rsp.status_code == 200, 'Response code is %s' % rsp.status_code

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_object, data)
        assert not errors

        assert len(data) == 0
