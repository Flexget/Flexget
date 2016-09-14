from __future__ import unicode_literals, division, absolute_import
from collections import deque

from flask import jsonify

from flexget.api.app import api

base_message = {
    'type': 'object',
    'properties': {
        'status_code': {'type': 'integer'},
        'message': {'type': 'string'},
        'status': {'type': 'string'}
    }
}

base_message_schema = api.schema('base_message', base_message)


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


class CannotAddResource(APIError):
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

    response_model = api.inherit('validation_error', APIError.response_model, {
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
@api.errorhandler(CannotAddResource)
@api.errorhandler(NotModified)
@api.errorhandler(PreconditionFailed)
def api_errors(error):
    return error.to_dict(), error.status_code
