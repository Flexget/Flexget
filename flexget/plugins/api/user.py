from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flask import request
from flask.ext.login import current_user

from flexget.api import api, APIResource
from flexget.webserver import change_password, generate_token, WeakPassword

user_api = api.namespace('user', description='Manage user login credentials')

user_password_input = {
    'type': 'object',
    'properties': {
        'password': {'type': 'string'}
    }
}
user_password_input_schema = api.schema('user_password_input', user_password_input)

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

empty_response = api.schema('empty', {'type': 'object'})


@user_api.route('/')
@api.doc('Change user password')
class UserManagementAPI(APIResource):
    @api.validate(model=user_password_input_schema, description='Password change schema')
    @api.response(500, 'Password not strong enough', default_error_schema)
    @api.response(200, 'Success', empty_response)
    @api.doc(description='Change user password. A medium strength password is required.'
                         ' See https://github.com/lepture/safe for reference')
    def put(self, session=None):
        """ Change user password """
        user = current_user
        data = request.json
        try:
            change_password(username=user.name, password=data.get('password'), session=session)
        except WeakPassword as e:
            return {'status': 'error',
                    'message': e.value}, 500
        return {'status': 'success',
                'message': 'Successfully changed user password'}


user_token_response = {
    'type': 'object',
    'properties': {
        'token': {'type': 'string'}
    }
}

user_token_response_schema = api.schema('user_token_response', user_token_response)


@user_api.route('/token/')
@api.doc('Change user token')
class UserManagementAPI(APIResource):
    @api.response(200, 'Successfully changed user token', user_token_response_schema)
    @api.doc(description='Get new user token')
    def get(self, session=None):
        """ Change current user token """
        token = generate_token(username=current_user.name, session=session)
        return {'token': token}
