import pytest

from flexget.components.imdb.api import ObjectsContainer as OC
from flexget.utils import json


@pytest.mark.online
class TestIMDBLookupAPI:
    config = 'tasks: {}'

    def test_imdb_search(self, api_client, schema_match):
        # No params
        rsp = api_client.get('/imdb/search/')
        assert rsp.status_code == 404, f'Response code is {rsp.status_code}'

        # Lookup by title
        rsp = api_client.get('/imdb/search/saw/')
        assert rsp.status_code == 200, f'Response code is {rsp.status_code}'

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_object, data)
        assert not errors
        assert len(data) > 1

        # Lookup by IMDB ID
        rsp = api_client.get('/imdb/search/tt0234215/')
        assert rsp.status_code == 200, f'Response code is {rsp.status_code}'

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_object, data)
        assert not errors

        assert len(data) == 1

        # Lookup non-existing title
        rsp = api_client.get('/imdb/search/sdfgsdfgsdfgsdfg/')
        assert rsp.status_code == 200, f'Response code is {rsp.status_code}'

        data = json.loads(rsp.get_data(as_text=True))
        errors = schema_match(OC.return_object, data)
        assert not errors

        assert len(data) == 0
