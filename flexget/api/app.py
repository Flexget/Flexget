from __future__ import unicode_literals, division, absolute_import

import logging
import os
from functools import wraps

from flask import Flask
from flask import request
from flask_compress import Compress
from flask_cors import CORS
from flask_restplus import Model, Api as RestPlusAPI
from flexget.api.responses import ValidationError, APIError
from flexget.config_schema import process_config
from flexget.utils.database import with_session
from flexget.webserver import User
from jsonschema import RefResolutionError

__version__ = '0.6-beta'

log = logging.getLogger('api')


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


class API(RestPlusAPI):
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
        return super(API, self).inherit(name, parent, fields)

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
        return super(API, self).response(code_or_apierror, description, model=model, **kwargs)


api_app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__path__[0]), 'templates'))
api_app.config['REMEMBER_COOKIE_NAME'] = 'flexgetToken'
api_app.config['DEBUG'] = True
api_app.config['ERROR_404_HELP'] = False

CORS(api_app)
Compress(api_app)

api = API(
    api_app,
    title='API',
    version=__version__,
    description='<font color="red"><b>Warning: under development, subject to change without notice.<b/></font>'
)


@with_session
def api_key(session=None):
    log.debug('fetching token for internal lookup')
    return session.query(User).first().token
