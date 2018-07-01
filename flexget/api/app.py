from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json
import logging
import os
import re
from collections import deque
from functools import wraps, partial

from flask import Flask, request, jsonify, make_response
from flask_compress import Compress
from flask_cors import CORS
from flask_restplus import Api as RestPlusAPI, Resource
from jsonschema import RefResolutionError
from werkzeug.http import generate_etag

from flexget import manager
from flexget.config_schema import process_config, format_checker
from flexget.utils.database import with_session
from flexget.webserver import User
from . import __path__

__version__ = '1.4.3'

log = logging.getLogger('api')


class APIClient(object):
    """
    This is an client which can be used as a more pythonic interface to the rest api.

    It skips http, and is only usable from within the running flexget process.
    """

    def __init__(self):
        self.app = api_app.test_client()

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


def api_version(f):
    """ Add the 'API-Version' header to all responses """

    @wraps(f)
    def wrapped(*args, **kwargs):
        rv = f(*args, **kwargs)
        rv.headers['API-Version'] = __version__
        return rv

    return wrapped


class APIResource(Resource):
    """All api resources should subclass this class."""
    method_decorators = [with_session, api_version]

    def __init__(self, api, *args, **kwargs):
        self.manager = manager.manager
        super(APIResource, self).__init__(api, *args, **kwargs)


class API(RestPlusAPI):
    """
    Extends a flask restplus :class:`flask_restplus.Api` with:
      - methods to make using json schemas easier
      - methods to auto document and handle :class:`ApiError` responses
    """

    def validate(self, model, schema_override=None, description=None):
        """
        When a method is decorated with this, json data submitted to the endpoint will be validated with the given
        `model`. This also auto-documents the expected model, as well as the possible :class:`ValidationError` response.
        """

        def decorator(func):
            @api.expect((model, description))
            @api.response(ValidationError)
            @wraps(func)
            def wrapper(*args, **kwargs):
                payload = request.json
                try:
                    schema = schema_override if schema_override else model.__schema__
                    errors = process_config(config=payload, schema=schema, set_defaults=False)

                    if errors:
                        raise ValidationError(errors)
                except RefResolutionError as e:
                    raise APIError(str(e))
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def response(self, code_or_apierror, description='Success', model=None, **kwargs):
        """
        Extends :meth:`flask_restplus.Api.response` to allow passing an :class:`ApiError` class instead of
        response code. If an `ApiError` is used, the response code, and expected response model, is automatically
        documented.
        """
        try:
            if issubclass(code_or_apierror, APIError):
                description = code_or_apierror.description or description
                return self.doc(
                    responses={code_or_apierror.status_code: (description, code_or_apierror.response_model)}, **kwargs)
        except TypeError:
            # If first argument isn't a class this happens
            pass
        return self.doc(responses={code_or_apierror: (description, model)}, **kwargs)

    def pagination_parser(self, parser=None, sort_choices=None, default=None, add_sort=None):
        """
        Return a standardized pagination parser, to be used for any endpoint that has pagination.

        :param RequestParser parser: Can extend a given parser or create a new one
        :param tuple sort_choices: A tuple of strings, to be used as server side attribute searches
        :param str default: The default sort string, used `sort_choices[0]` if not given
        :param bool add_sort: Add sort order choices without adding specific sort choices

        :return: An api.parser() instance with pagination and sorting arguments.
        """
        pagination = parser.copy() if parser else self.parser()
        pagination.add_argument('page', type=int, default=1, help='Page number')
        pagination.add_argument('per_page', type=int, default=50, help='Results per page')
        if sort_choices or add_sort:
            pagination.add_argument('order', choices=('desc', 'asc'), default='desc', help='Sorting order')
        if sort_choices:
            pagination.add_argument('sort_by', choices=sort_choices, default=default or sort_choices[0],
                                    help='Sort by attribute')

        return pagination


api_app = Flask(__name__, template_folder=os.path.join(__path__[0], 'templates'))
api_app.config['REMEMBER_COOKIE_NAME'] = 'flexget.token'
api_app.config['DEBUG'] = True
api_app.config['ERROR_404_HELP'] = False
api_app.url_map.strict_slashes = False

CORS(api_app, expose_headers='Link, Total-Count, Count, ETag')
Compress(api_app)

api = API(
    api_app,
    title='Flexget API v{}'.format(__version__),
    version=__version__,
    description='View and manage flexget core operations and plugins. Open each endpoint view for usage information.'
                ' Navigate to http://flexget.com/API for more details.',
    format_checker=format_checker
)

base_message = {
    'type': 'object',
    'properties': {
        'status_code': {'type': 'integer'},
        'message': {'type': 'string'},
        'status': {'type': 'string'}
    },
    'required': ['status_code', 'message', 'status']

}

base_message_schema = api.schema_model('base_message', base_message)


class APIError(Exception):
    description = 'Server error'
    status_code = 500
    status = 'Error'
    response_model = base_message_schema

    def __init__(self, message=None, payload=None):
        self.message = message
        self.payload = payload

    def to_dict(self):
        rv = self.payload or {}
        rv.update(status_code=self.status_code, message=self.message, status=self.status)
        return rv

    @classmethod
    def schema(cls):
        return cls.response_model.__schema__


class NotFoundError(APIError):
    status_code = 404
    description = 'Not found'


class Unauthorized(APIError):
    status_code = 401
    description = 'Unauthorized'


class BadRequest(APIError):
    status_code = 400
    description = 'Bad request'


class Conflict(APIError):
    status_code = 409
    description = 'Conflict'


class PreconditionFailed(APIError):
    status_code = 412
    description = 'Precondition failed'


class NotModified(APIError):
    status_code = 304
    description = 'not modified'


class ValidationError(APIError):
    status_code = 422
    description = 'Validation error'

    response_model = api.schema_model('validation_error', {
        'type': 'object',
        'properties': {
            'validation_errors': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string', 'description': 'A human readable message explaining the error.'},
                        'validator': {'type': 'string', 'description': 'The name of the failed validator.'},
                        'validator_value': {
                            'type': 'string', 'description': 'The value for the failed validator in the schema.'
                        },
                        'path': {'type': 'string'},
                        'schema_path': {'type': 'string'},
                    }
                }
            }
        },
        'required': ['validation_errors']
    })

    verror_attrs = (
        'message', 'cause', 'validator', 'validator_value',
        'path', 'schema_path', 'parent'
    )

    def __init__(self, validation_errors, message='validation error'):
        payload = {'validation_errors': [self._verror_to_dict(error) for error in validation_errors]}
        super(ValidationError, self).__init__(message, payload=payload)

    def _verror_to_dict(self, error):
        error_dict = {}
        for attr in self.verror_attrs:
            if isinstance(getattr(error, attr), deque):
                error_dict[attr] = list(getattr(error, attr))
            else:
                error_dict[attr] = str(getattr(error, attr))
        return error_dict


empty_response = api.schema_model('empty', {'type': 'object'})


def success_response(message, status_code=200, status='success'):
    rsp_dict = {
        'message': message,
        'status_code': status_code,
        'status': status
    }
    rsp = jsonify(rsp_dict)
    rsp.status_code = status_code
    return rsp


@api.errorhandler(APIError)
@api.errorhandler(NotFoundError)
@api.errorhandler(ValidationError)
@api.errorhandler(BadRequest)
@api.errorhandler(Unauthorized)
@api.errorhandler(Conflict)
@api.errorhandler(NotModified)
@api.errorhandler(PreconditionFailed)
def api_errors(error):
    return error.to_dict(), error.status_code


@with_session
def api_key(session=None):
    log.debug('fetching token for internal lookup')
    return session.query(User).first().token


def etag(method=None, cache_age=0):
    """
    A decorator that add an ETag header to the response and checks for the "If-Match" and "If-Not-Match" headers to
     return an appropriate response.

    :param method: A GET or HEAD flask method to wrap
    :param cache_age: max-age cache age for the content
    :return: The method's response with the ETag and Cache-Control headers, raises a 412 error or returns a 304 response
    """

    # If called without method, we've been called with optional arguments.
    # We return a decorator with the optional arguments filled in.
    # Next time round we'll be decorating method.
    if method is None:
        return partial(etag, cache_age=cache_age)

    @wraps(method)
    def wrapped(*args, **kwargs):
        # Identify if this is a GET or HEAD in order to proceed
        assert request.method in ['HEAD', 'GET'], '@etag is only supported for GET requests'
        rv = method(*args, **kwargs)
        rv = make_response(rv)

        # Some headers can change without data change for specific page
        content_headers = rv.headers.get('link', '') + rv.headers.get('count', '') + rv.headers.get('total-count', '')
        data = (rv.get_data().decode() + content_headers).encode()
        etag = generate_etag(data)
        rv.headers['Cache-Control'] = 'max-age=%s' % cache_age
        rv.headers['ETag'] = etag
        if_match = request.headers.get('If-Match')
        if_none_match = request.headers.get('If-None-Match')

        if if_match:
            etag_list = [tag.strip() for tag in if_match.split(',')]
            if etag not in etag_list and '*' not in etag_list:
                raise PreconditionFailed('etag does not match')
        elif if_none_match:
            etag_list = [tag.strip() for tag in if_none_match.split(',')]
            if etag in etag_list or '*' in etag_list:
                raise NotModified

        return rv

    return wrapped


def pagination_headers(total_pages, total_items, page_count, request):
    """
    Creates the `Link`. 'Count' and  'Total-Count' headers, to be used for pagination traversing

    :param total_pages: Total number of pages
    :param total_items: Total number of items in all the pages
    :param page_count: Item count for page (may differ from page size request)
    :param request: The flask request used, required to build other reoccurring vars like url and such.
    :return:
    """

    # Build constant variables from request data
    url = request.url_root + request.path.lstrip('/')
    per_page = request.args.get('per_page', 50)
    page = int(request.args.get('page', 1))

    # Build the base template
    LINKTEMPLATE = '<{}?per_page={}&'.format(url, per_page)

    # Removed page and per_page from query string
    query_string = re.sub(b'per_page=\d+', b'', request.query_string)
    query_string = re.sub(b'page=\d+', b'', query_string)
    query_string = re.sub(b'&{2,}', b'&', query_string)

    # Add all original query params
    LINKTEMPLATE += query_string.decode().lstrip('&') + '&page={}>; rel="{}"'

    link_string = ''

    if page > 1:
        link_string += LINKTEMPLATE.format(page - 1, 'prev') + ', '
    if page < total_pages:
        link_string += LINKTEMPLATE.format(page + 1, 'next') + ', '
    link_string += LINKTEMPLATE.format(total_pages, 'last')

    return {
        'Link': link_string,
        'Total-Count': total_items,
        'Count': page_count
    }
