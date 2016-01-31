from __future__ import unicode_literals, division, absolute_import

import datetime
from math import ceil

from flask.ext.login import login_user, LoginManager, current_user, current_app
from flask import jsonify
from flask import request
from flask_restplus import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource
from flexget.plugins.filter import series
from flexget.webserver import change_password
import requests

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
    @api.validate(model=user_password_input_schema, description='test')
    def put(self, session=None):
        """ Change user password """
        user = current_user
        data = request.json
        change_password(user_name=user.name, password=data.get('password'), session=session)
        return {'status': 'success',
                'message': 'Successfully changed user password'}
