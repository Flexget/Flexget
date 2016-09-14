import json

from flask_restplus import Resource
from flexget import manager

from flexget.api import app, api_key
from flexget.utils.database import with_session


class APIClient(object):
    """
    This is an client which can be used as a more pythonic interface to the rest api.

    It skips http, and is only usable from within the running flexget process.
    """

    def __init__(self):
        self.app = app.test_client()

    def __getattr__(self, item):
        return APIEndpoint('/api/' + item, self.get_endpoint)

    def get_endpoint(self, url, data=None, method=None):
        if method is None:
            method = 'POST' if data is not None else 'GET'
        auth_header = dict(Authorization='Token %s' % api_key())
        response = self.app.open(url, data=data, follow_redirects=True, method=method, headers=auth_header)
        result = json.loads(response.get_data(as_text=True))
        # TODO: Proper exceptions
        if 200 > response.status_code >= 300:
            raise Exception(result['error'])
        return result


class APIEndpoint(object):
    def __init__(self, endpoint, caller):
        self.endpoint = endpoint
        self.caller = caller

    def __getattr__(self, item):
        return self.__class__(self.endpoint + '/' + item, self.caller)

    __getitem__ = __getattr__

    def __call__(self, data=None, method=None):
        return self.caller(self.endpoint, data=data, method=method)


class APIResource(Resource):
    """All api resources should subclass this class."""
    method_decorators = [with_session]

    def __init__(self, api, *args, **kwargs):
        self.manager = manager.manager
        super(APIResource, self).__init__(api, *args, **kwargs)