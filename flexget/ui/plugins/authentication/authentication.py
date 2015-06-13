from __future__ import unicode_literals, division, absolute_import
import logging

from sqlalchemy import Column, Unicode
from flask import Blueprint, request, Response

from flexget.event import event
from flexget.ui import register_plugin, manager, webui_app
from flexget.manager import Base


log = logging.getLogger('ui.authentication')
auth = Blueprint('authentication', __name__)
credentials = None

class AuthCredentials(Base):
    __tablename__ = 'authentication'

    username = Column(Unicode, primary_key=True)
    password = Column(Unicode)

    def __init__(self, username, password):
        self.username = username
        self.password = password


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == credentials.username and password == credentials.password


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {b'WWW-Authenticate': b'Basic realm="Login Required"'})


@event('webui.start')
def enable_authentication():

    webui_config = manager.config.get('webui', False)

    # Not enabled
    if not webui_config:
        return

    auth_config = webui_config.get('authentication')

    if not auth_config:
        log.warning("Authentication disabled, not recommended for security reasons!")
        return

    global credentials
    credentials = db_session.query(AuthCredentials).first()

    if not credentials:
        credentials = AuthCredentials('flexget', 'flexget')
        db_session.add(credentials)

    if auth_config.get("username"):
        credentials.username = auth_config['username']
    if auth_config.get("password"):
        credentials.password = auth_config['password']
    db_session.commit()

    app.before_request(check_authenticated)


def check_authenticated():
    # TODO: Is this a big security hole? Maybe figure out a better way to authenticate for local IPC
    if request.remote_addr == '127.0.0.1':
        if not config['authentication'] or config['authentication']['no_local_auth']:
            return

    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()


#register_plugin(auth)