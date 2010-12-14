import logging
from flask import Module, request, Response
from flexget.event import event
from flexget.ui.webui import register_plugin, app, manager

log = logging.getLogger('ui.schedule')
auth = Module(__name__)


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == manager.options.username and password == manager.options.password


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


@event('webui.start')
def enable_authentication():
    app.before_request(check_authentication)


def check_authentication():
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()


register_plugin(auth)
