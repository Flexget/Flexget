from __future__ import unicode_literals, division, absolute_import
import logging
from sqlalchemy import Column, Unicode
from flask import Module, request, Response
from flexget.event import event
from flexget.ui.webui import register_plugin, app, manager, db_session
from flexget.manager import Base

log = logging.getLogger('ui.authentication')
auth = Module(__name__)
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
    if manager.options.no_auth:
        return
    global credentials
    credentials = db_session.query(AuthCredentials).first()
    if not credentials:
        credentials = AuthCredentials('flexget', 'flexget')
        db_session.add(credentials)

    if manager.options.username:
        credentials.username = manager.options.username
    if manager.options.password:
        credentials.password = manager.options.password
    db_session.commit()

    app.before_request(check_authenticated)


def check_authenticated():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()


register_plugin(auth)
