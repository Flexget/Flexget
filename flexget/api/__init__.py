import logging
import json
import os
import pkgutil

from functools import wraps
from collections import deque

from flask import Flask, request, jsonify
from flask_restplus import Api as RestPlusAPI
from flask_restplus.resource import Resource
from flask_restplus.model import ApiModel
from flask_compress import Compress
from jsonschema.exceptions import RefResolutionError
from werkzeug.exceptions import HTTPException

from flexget.event import event
from flexget.webserver import register_app, get_secret
from flexget.config_schema import process_config, register_config_key
from flexget import manager
from flexget.utils.database import with_session

__version__ = '0.1-alpha'

log = logging.getLogger('api')

api_config = {}
api_config_schema = {
    'type': 'boolean',
    'additionalProperties': False
}


@event('config.register')
def register_config():
    register_config_key('api', api_config_schema)


class ApiSchemaModel(ApiModel):
    """A flask restplus :class:`flask_restplus.models.ApiModel` which can take a json schema directly."""
    def __init__(self, schema, *args, **kwargs):
        self._schema = schema
        super(ApiSchemaModel, self).__init__()

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

    def __repr__(self):
        return '<ApiSchemaModel(%r)>' % self._schema


class Api(RestPlusAPI):
    """
    Extends a flask restplus :class:`flask_restplus.Api` with:
      - methods to make using json schemas easier
      - methods to auto document and handle :class:`ApiError` responses
    """

    def schema(self, name, schema, **kwargs):
        """
        Register a json schema.

        Usable like :meth:`flask_restplus.Api.model`, except takes a json schema as its argument.

        :returns: An :class:`ApiSchemaModel` instance registered to this api.
        """
        return self.model(name, **kwargs)(ApiSchemaModel(schema))

    def inherit(self, name, parent, fields):
        """
        Extends :meth:`flask_restplus.Api.inherit` to allow `fields` to be a json schema, if `parent` is a
        :class:`ApiSchemaModel`.
        """
        if isinstance(parent, ApiSchemaModel):
            model = ApiSchemaModel(fields)
            model.__apidoc__['name'] = name
            model.__parent__ = parent
            self.models[name] = model
            return model
        return super(Api, self).inherit(name, parent, fields)

    def validate(self, model):
        """
        When a method is decorated with this, json data submitted to the endpoint will be validated with the given
        `model`. This also auto-documents the expected model, as well as the possible :class:`ValidationError` response.
        """
        def decorator(func):
            @api.expect(model)
            @api.response(ValidationError)
            @wraps(func)
            def wrapper(*args, **kwargs):
                payload = request.json
                try:
                    errors = process_config(config=payload, schema=model.__schema__, set_defaults=False)
                    if errors:
                        raise ValidationError(errors)
                except RefResolutionError as e:
                    raise ApiError(str(e))
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def response(self, code_or_apierror, description=None, model=None, **kwargs):
        """
        Extends :meth:`flask_restplus.Api.response` to allow passing an :class:`ApiError` class instead of
        response code. If an `ApiError` is used, the response code, and expected response model, is automatically
        documented.
        """
        try:
            if issubclass(code_or_apierror, ApiError):
                description = description or code_or_apierror.description
                return self.doc(responses={code_or_apierror.code: (description, code_or_apierror.response_model)})
        except TypeError:
            # If first argument isn't a class this happens
            pass
        return super(Api, self).response(code_or_apierror, description)

    def handle_error(self, error):
        """Responsible for returning the proper response for errors in api methods."""
        if isinstance(error, ApiError):
            return jsonify(error.to_dict()), error.code
        elif isinstance(error, HTTPException):
            return jsonify({'code': error.code, 'error': error.description}), error.code
        return super(Api, self).handle_error(error)


class APIResource(Resource):
    """All api resources should subclass this class."""
    method_decorators = [with_session]

    def __init__(self):
        self.manager = manager.manager
        super(APIResource, self).__init__()


app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__path__[0]), 'templates'))
app.config['REMEMBER_COOKIE_NAME'] = 'flexgetToken'

Compress(app)
api = Api(
    app,
    catch_all_404s=True,
    title='API',
    version=__version__,
    description='<font color="red"><b>Warning: under development, subject to change without notice.<b/></font>'
)


class ApiError(Exception):
    code = 500
    description = 'server error'

    response_model = api.schema('error', {
        'type': 'object',
        'properties': {
            'code': {'type': 'integer'},
            'error': {'type': 'string'}
        },
        'required': ['code', 'error']
    })

    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload

    def to_dict(self):
        rv = self.payload or {}
        rv.update(code=self.code, error=self.message)
        return rv

    @classmethod
    def schema(cls):
        return cls.response_model.__schema__


class NotFoundError(ApiError):
    code = 404
    description = 'not found'


class ValidationError(ApiError):
    code = 400
    description = 'validation error'

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
                error_dict[attr] = getattr(error, attr)
        return error_dict


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
        app = Flask(__name__)
        app.register_blueprint(api)
        self.app = app.test_client()

    def __getattr__(self, item):
        return ApiEndopint('/api/' + item, self.get_endpoint)

    def get_endpoint(self, url, data, method=None):
        if method is None:
            method = 'POST' if data is not None else 'GET'
        response = self.app.open(url, data=data, follow_redirects=True, method=method)
        result = json.loads(response.data)
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
