from __future__ import unicode_literals, division, absolute_import

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


@user_api.route('/')
@api.doc('Change user password')
class UserManagementAPI(APIResource):
    @api.validate(model=user_password_input_schema, description='Password change schema')
    @api.response(400, 'Password not strong enough')
    def put(self, session=None):
        """ Change user password """
        user = current_user
        data = request.json
        try:
            change_password(user_name=user.name, password=data.get('password'), session=session)
        except WeakPassword as e:
            return {'status': 'error',
                    'message': e.value}, 400
        return {'status': 'success',
                'message': 'Successfully changed user password'}


user_token_response = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'},
        'token': {'type': 'string'}
    }
}

user_token_response_schema = api.schema('user_token_response', user_token_response)


@user_api.route('/token/')
@api.doc('Change user token')
class UserManagementAPI(APIResource):
    @api.response(200, 'Successfully changed user token', user_token_response_schema)
    def get(self, session=None):
        """ Change current user token """
        user = generate_token(user_name=current_user.name, session=session)
        return {'status': 'success',
                'message': 'Successfully changed user token',
                'token': user.token}
