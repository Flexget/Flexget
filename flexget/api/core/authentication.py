from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import base64

from flask import request, session as flask_session
from flask_login import LoginManager
from flask_login.utils import current_app, login_user, current_user
from flask_restplus import inputs
from werkzeug.security import check_password_hash

from flexget.api import api_app
from flexget.api.app import Unauthorized, success_response, base_message_schema, api, APIResource
from flexget.utils.database import with_session
from flexget.webserver import User

login_manager = LoginManager()
login_manager.init_app(api_app)


@login_manager.request_loader
@with_session
def load_user_from_request(request, session=None):
    auth_value = request.headers.get('Authorization')

    if not auth_value:
        return

    # Login using api key
    if auth_value.startswith('Token'):
        try:
            token = auth_value.replace('Token ', '', 1)
            return session.query(User).filter(User.token == token).first()
        except (TypeError, ValueError):
            pass

    # Login using basic auth
    if auth_value.startswith('Basic'):
        try:
            credentials = base64.b64decode(auth_value.replace('Basic ', '', 1))
            username, password = credentials.split(':')
            user = session.query(User).filter(User.name == username).first()
            if user and user.password and check_password_hash(user.password, password):
                return user
            else:
                return None
        except (TypeError, ValueError):
            pass


@login_manager.user_loader
@with_session
def load_user(username, session=None):
    return session.query(User).filter(User.name == username).first()


@api_app.before_request
def check_valid_login():
    # Allow access to root, login and swagger documentation without authentication
    if (
        request.path == '/'
        or request.path.startswith('/auth/login')
        or request.path.startswith('/auth/logout')
        or request.path.startswith('/swagger')
        or request.method == 'OPTIONS'
    ):
        return

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()


# API Authentication and Authorization
auth_api = api.namespace('auth', description='Authentication')

login_api_schema = api.schema_model(
    'auth.login',
    {
        'type': 'object',
        'properties': {'username': {'type': 'string'}, 'password': {'type': 'string'}},
        'required': ['username', 'password'],
        'additionalProperties': False,
    },
)

login_parser = api.parser()
login_parser.add_argument(
    'remember',
    type=inputs.boolean,
    required=False,
    default=False,
    help='Remember login (sets persistent session cookies)',
)


@auth_api.route('/login/')
class LoginAPI(APIResource):
    @api.validate(login_api_schema, description='Username and Password')
    @api.response(Unauthorized)
    @api.response(200, 'Login successful', model=base_message_schema)
    @api.doc(parser=login_parser)
    def post(self, session=None):
        """ Login with username and password """
        data = request.json
        user_name = data.get('username')
        password = data.get('password')

        if data:
            user = session.query(User).filter(User.name == user_name.lower()).first()
            if user:
                if user_name == 'flexget' and not user.password:
                    raise Unauthorized(
                        'If this is your first time running the WebUI you need to set a password via'
                        ' the command line by running `flexget web passwd <new_password>`'
                    )

                if user.password and check_password_hash(user.password, password):
                    args = login_parser.parse_args()
                    login_user(user, remember=args['remember'])
                    return success_response('user logged in')

        raise Unauthorized('Invalid username or password')


@auth_api.route('/logout/')
class LogoutAPI(APIResource):
    @api.response(200, 'Logout successful', model=base_message_schema)
    def post(self, session=None):
        """ Logout and clear session cookies """
        flask_session.clear()
        resp = success_response('User logged out')
        resp.set_cookie('flexget.token', '', expires=0)
        return resp
