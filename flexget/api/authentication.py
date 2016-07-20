from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import base64

from flask import request, jsonify, session as flask_session
from flask_login import login_user, LoginManager, current_user, current_app
from flask_restplus import inputs
from werkzeug.security import check_password_hash

from flexget.api import api, APIResource, app
from flexget.utils.database import with_session
from flexget.webserver import User

login_manager = LoginManager()
login_manager.init_app(app)


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


@app.before_request
def check_valid_login():
    # Allow access to root, login and swagger documentation without authentication
    if request.path == '/' or request.path.startswith('/auth/login') or \
            request.path.startswith('/auth/logout') or request.path.startswith('/swagger'):
        return

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()


# API Authentication and Authorization
auth_api = api.namespace('auth', description='Authentication')

login_api_schema = api.schema('auth.login', {
    'type': 'object',
    'properties': {
        'username': {'type': 'string'},
        'password': {'type': 'string'}
    }
})

login_parser = api.parser()
login_parser.add_argument('remember', type=inputs.boolean, required=False, default=False,
                          help='Remember login (sets persistent session cookies)'
                          )


@auth_api.route('/login/')
class LoginAPI(APIResource):

    @api.expect((login_api_schema, 'Username and Password'))
    @api.response(401, 'Invalid username or password')
    @api.response(200, 'Login successful')
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
                    return {
                        'status': 'failed',
                        'message': 'If this is your first time running the webui you need to set a password via'
                        ' the command line by running flexget web passwd <new_password>'
                    }, 401

                if user.password and check_password_hash(user.password, password):
                    args = login_parser.parse_args()
                    login_user(user, remember=args['remember'])
                    return {}

        return {'status': 'failed', 'message': 'Invalid username or password'}, 401


@auth_api.route('/logout/')
class LogoutAPI(APIResource):

    @api.response(200, 'Logout successful')
    def get(self, session=None):
        """ Logout and clear session cookies """
        flask_session.clear()
        resp = jsonify({})
        resp.set_cookie('flexgetToken', '', expires=0)
        return resp
