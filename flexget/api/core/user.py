from flask import Response, jsonify, request
from flask_login import current_user
from sqlalchemy.orm import Session

from flexget.api import APIResource, api
from flexget.api.app import BadRequest, base_message_schema, success_response
from flexget.webserver import WeakPassword, change_password, generate_token

user_api = api.namespace('user', description='Manage user login credentials')


class ObjectsContainer:
    user_password_input = {
        'type': 'object',
        'properties': {'password': {'type': 'string'}},
        'required': ['password'],
        'additionalProperties': False,
    }

    user_token_response = {'type': 'object', 'properties': {'token': {'type': 'string'}}}


user_password_input_schema = api.schema_model(
    'user_password_input', ObjectsContainer.user_password_input
)
user_token_response_schema = api.schema_model(
    'user_token_response', ObjectsContainer.user_token_response
)


@user_api.route('/')
@api.doc('Change user password')
class UserManagementAPI(APIResource):
    @api.validate(model=user_password_input_schema, description='Password change schema')
    @api.response(BadRequest)
    @api.response(200, 'Success', model=base_message_schema)
    @api.doc(
        description='Change user password. A score of at least 3 is needed.'
        'See https://github.com/dropbox/zxcvbn for details'
    )
    def put(self, session: Session = None) -> Response:
        """Change user password"""
        user = current_user
        data = request.json
        try:
            change_password(username=user.name, password=data.get('password'), session=session)
        except WeakPassword as e:
            raise BadRequest(e.value)
        return success_response('Successfully changed user password')


@user_api.route('/token/')
@api.doc('Change user token')
class UserManagementTokenAPI(APIResource):
    @api.response(200, 'Successfully got user token', user_token_response_schema)
    @api.doc(description='Get current user token')
    def get(self, session: Session = None) -> Response:
        token = current_user.token
        return jsonify({'token': token})

    @api.response(200, 'Successfully changed user token', user_token_response_schema)
    @api.doc(description='Get new user token')
    def put(self, session: Session = None) -> Response:
        """Change current user token"""
        token = generate_token(username=current_user.name, session=session)
        return jsonify({'token': token})
