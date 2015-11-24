import base64

from flask import request, jsonify, session as flask_session
from flask.ext.login import login_user, LoginManager, current_user, current_app

from flexget.api import api, APIResource, app
from flexget.webserver import User
from flexget.utils.database import with_session

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
            return session.query(User).filter(User.name == username, User.password == password).first()
        except (TypeError, ValueError):
            pass


@login_manager.user_loader
@with_session
def load_user(username, session=None):
    return session.query(User).filter(User.name == username).first()


@app.before_request
def check_valid_login():
    # Allow access to root, login and swagger documentation without authentication
    if request.path == '/' or request.path.startswith('/login') or \
            request.path.startswith('/logout') or request.path.startswith('/swagger'):
        return

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()

# API Authentication and Authorization
login_api = api.namespace('login', description='API Authentication')

login_api_schema = api.schema('login', {
    'type': 'object',
    'properties': {
        'username': {'type': 'string'},
        'password': {'type': 'string'}
    }
})

login_parser = api.parser()
login_parser.add_argument('remember', type=bool, required=False, default=False, help='Remember for next time')


@login_api.route('/')
@api.doc(description='Login to API with username and password')
class LoginAPI(APIResource):

    @api.expect(login_api_schema)
    @api.response(400, 'Invalid username or password')
    @api.response(200, 'Login successful')
    @api.doc(parser=login_parser)
    def post(self, session=None):
        data = request.json

        if data:
            user = session.query(User)\
                .filter(User.name == data.get('username').lower(), User.password == data.get('password'))\
                .first()

            if user:
                args = login_parser.parse_args()
                login_user(user, remember=args['remember'])
                return {'status': 'success'}

        return {'status': 'failed', 'message': 'Invalid username or password'}, 400


logout_api = api.namespace('logout', description='API Authentication')


@logout_api.route('/')
@api.doc(description='Logout and clear session cookies')
class LogoutAPI(APIResource):

    @api.response(200, 'Logout successful')
    def get(self, session=None):
        flask_session.clear()
        resp = jsonify({'status': 'success'})
        resp.set_cookie('flexgetToken', '', expires=0)
        return resp