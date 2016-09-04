from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import json
import logging
import os
import pkgutil
from collections import deque
from functools import wraps

from flask import Flask, request
from flask_cors import CORS
from flask_compress import Compress
from flask_restplus import Api as RestPlusAPI
from flask_restplus.model import Model
from flask_restplus.resource import Resource
from jsonschema.exceptions import RefResolutionError

from flexget import manager
from flexget.config_schema import process_config, register_config_key
from flexget.event import event
from flexget.utils.database import with_session
from flexget.webserver import User
from flexget.webserver import register_app, get_secret

__version__ = '0.6-beta'

log = logging.getLogger('api')

api_config = {}
api_config_schema = {
    'type': 'boolean',
    'additionalProperties': False
}


@with_session
def api_key(session=None):
    log.debug('fetching token for internal lookup')
    return session.query(User).first().token


@event('config.register')
def register_config():
    register_config_key('api', api_config_schema)


class ApiSchemaModel(Model):
    """A flask restplus :class:`flask_restplus.models.ApiModel` which can take a json schema directly."""

    def __init__(self, name, schema, *args, **kwargs):
        super(ApiSchemaModel, self).__init__(name, *args, **kwargs)
        self._schema = schema

    @property
    def __schema__(self):
        if self.__parent__:
            return {
                'allOf': [
                    {'$ref': '#/definitions/{0}'.format(self.__parent__.name)},
                    self._schema
                ]
            }
        else:
            return self._schema

    def __nonzero__(self):
        return bool(self._schema)

    def __bool__(self):
        return self._schema is not None

    def __repr__(self):
        return '<ApiSchemaModel(%r)>' % self._schema


class Api(RestPlusAPI):
    """
    Extends a flask restplus :class:`flask_restplus.Api` with:
      - methods to make using json schemas easier
      - methods to auto document and handle :class:`ApiError` responses
    """

    def _rewrite_refs(self, schema):
        if isinstance(schema, list):
            for value in schema:
                self._rewrite_refs(value)

        if isinstance(schema, dict):
            for key, value in schema.items():
                if isinstance(value, (list, dict)):
                    self._rewrite_refs(value)

                if key == '$ref' and value.startswith('/'):
                    schema[key] = '#definitions%s' % value

    def schema(self, name, schema, **kwargs):
        """
        Register a json schema.

        Usable like :meth:`flask_restplus.Api.model`, except takes a json schema as its argument.

        :returns: An :class:`ApiSchemaModel` instance registered to this api.
        """
        model = ApiSchemaModel(name, schema, **kwargs)
        model.__apidoc__.update(kwargs)
        self.models[name] = model
        return model

    def inherit(self, name, parent, fields):
        """
        Extends :meth:`flask_restplus.Api.inherit` to allow `fields` to be a json schema, if `parent` is a
        :class:`ApiSchemaModel`.
        """
        if isinstance(parent, ApiSchemaModel):
            model = ApiSchemaModel(name, fields)
            model.__apidoc__['name'] = name
            model.__parent__ = parent
            self.models[name] = model
            return model
        return super(Api, self).inherit(name, parent, fields)

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
                    raise ApiError(str(e))
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
            if issubclass(code_or_apierror, ApiError):
                description = code_or_apierror.description or description
                return self.doc(responses={code_or_apierror.code: (description, code_or_apierror.response_model)})
        except TypeError:
            # If first argument isn't a class this happens
            pass
        return super(Api, self).response(code_or_apierror, description, model=model)


class APIResource(Resource):
    """All api resources should subclass this class."""
    method_decorators = [with_session]

    def __init__(self, api, *args, **kwargs):
        self.manager = manager.manager
        super(APIResource, self).__init__(api, *args, **kwargs)


app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__path__[0]), 'templates'))
app.config['REMEMBER_COOKIE_NAME'] = 'flexgetToken'
app.config['DEBUG'] = True

CORS(app)
Compress(app)

api = Api(
    app,
    catch_all_404s=True,
    title='API',
    version=__version__,
    description='<font color="red"><b>Warning: under development, subject to change without notice.<b/></font>'
)


class ApiError(Exception):
    description = 'Server error'
    code = 500
    response_model = api.schema('error', {
        'type': 'object',
        'properties': {
            'code': {'type': 'integer'},
            'message': {'type': 'string'}
        },
        'required': ['code', 'error']
    })

    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload

    def to_dict(self):
        rv = self.payload or {}
        rv.update(code=self.code, message=self.message)
        return rv

    @classmethod
    def schema(cls):
        return cls.response_model.__schema__


class NotFoundError(ApiError):
    code = 404
    description = 'Not found'


class BadRequest(ApiError):
    code = 400
    description = 'Bad request'


class ValidationError(ApiError):
    code = 422
    description = 'Validation error'

    response_model = api.inherit('validation_error', ApiError.response_model, {
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

empty_response = api.schema('empty', {'type': 'object'})
default_error_schema = {
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'message': {'type': 'string'}
        }
    }
default_error_schema = api.schema('default_error_schema', default_error_schema)


@api.errorhandler(ApiError)
@api.errorhandler(NotFoundError)
@api.errorhandler(ValidationError)
@api.errorhandler(BadRequest)
def api_errors(error):
    return error.to_dict(), error.code


@event('manager.daemon.started')
def register_api(mgr):
    global api_config
    api_config = mgr.config.get('api')

    app.secret_key = get_secret()

    if api_config:
        register_app('/api', app)


class ApiClient(object):
    """
    This is an client which can be used as a more pythonic interface to the rest api.

    It skips http, and is only usable from within the running flexget process.
    """

    def __init__(self):
        self.app = app.test_client()

    def __getattr__(self, item):
        return ApiEndopint('/api/' + item, self.get_endpoint)

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


class ApiEndopint(object):

    def __init__(self, endpoint, caller):
        self.endpoint = endpoint
        self.caller = caller

    def __getattr__(self, item):
        return self.__class__(self.endpoint + '/' + item, self.caller)

    __getitem__ = __getattr__

    def __call__(self, data=None, method=None):
        return self.caller(self.endpoint, data=data, method=method)


# Import API Sub Modules
for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
    loader.find_module(module_name).load_module(module_name)
