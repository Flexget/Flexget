from __future__ import unicode_literals, division, absolute_import
import logging
import threading
import hashlib
import random
import socket

from sqlalchemy import Column, Integer, Unicode

from flask import Flask, abort, redirect
from flask.ext.login import UserMixin

from flexget import options, plugin
from flexget.event import event
from flexget.config_schema import register_config_key
from flexget.utils.tools import singleton
from flexget.manager import Base
from flexget.utils.database import with_session
from flexget.logger import console

log = logging.getLogger('web_server')

_home = None
_app_register = {}
_default_app = Flask(__name__)

random = random.SystemRandom()

web_config_schema = {
    'oneOf': [
        {'type': 'boolean'},
        {
            'type': 'object',
            'properties': {
                'bind': {'type': 'string', 'format': 'ipv4', 'default': '0.0.0.0'},
                'port': {'type': 'integer', 'default': 3539},
            },
            'additionalProperties': False
        }
    ]
}


def generate_key():
    """ Generate key for use to authentication """
    return unicode(hashlib.sha224(str(random.getrandbits(128))).hexdigest())


def get_random_string(length=12, allowed_chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
    """
    Returns a securely generated random string.

    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits.

    Taken from the django.utils.crypto module.
    """
    return ''.join(random.choice(allowed_chars) for __ in range(length))


@with_session
def get_secret(session=None):
    pass
    """ Generate a secret key for flask applications and store it in the database. """
    web_secret = session.query(WebSecret).first()
    if not web_secret:
        web_secret = WebSecret(id=1, value=get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'))
        session.add(web_secret)
        session.commit()

    return web_secret.value


class User(Base, UserMixin):
    """ User class available for flask apps to handle authentication using flask_login """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50), unique=True)
    token = Column(Unicode, default=generate_key)
    password = Column(Unicode)

    def __repr__(self):
        return '<User %r>' % self.name

    def get_id(self):
        return self.name


class WebSecret(Base):
    """ Store flask secret in the database """
    __tablename__ = 'secret'

    id = Column(Unicode, primary_key=True)
    value = Column(Unicode)


@event('config.register')
def register_config():
    register_config_key('web_server', web_config_schema)


def register_app(path, application):
    if path in _app_register:
        raise ValueError('path %s already registered')
    _app_register[path] = application


def register_home(route):
    """Registers UI home page"""
    global _home
    _home = route


@_default_app.route('/')
def start_page():
    """ Redirect user to registered UI home """
    if not _home:
        abort(404)
    return redirect(_home)


@event('manager.daemon.started', -255)  # Low priority so plugins can register apps
@with_session
def setup_server(manager, session=None):
    """ Sets up and starts/restarts the web service. """
    if not manager.is_daemon:
        return

    web_server_config = manager.config.get('web_server')

    if not web_server_config:
        return

    web_server = WebServer(
        bind=web_server_config['bind'],
        port=web_server_config['port'],
    )

    _default_app.secret_key = get_secret()

    # Create default flexget user
    if session.query(User).count() == 0:
        session.add(User(name="flexget", password="flexget"))
        session.commit()

    if web_server.is_alive():
        web_server.stop()

    if _app_register:
        web_server.start()


@event('manager.shutdown_requested')
def stop_server(manager):
    """ Sets up and starts/restarts the webui. """
    if not manager.is_daemon:
        return
    web_server = WebServer()
    if web_server.is_alive():
        web_server.stop()


@singleton
class WebServer(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(self, bind='0.0.0.0', port=5050):
        threading.Thread.__init__(self, name='web_server')
        self.bind = str(bind)  # String to remove unicode warning from cherrypy startup
        self.port = port
        self.server = None

    def start(self):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if not self.is_alive():
            self.__init__(bind=self.bind, port=self.port)
        threading.Thread.start(self)

    def _start_server(self):
        from cherrypy import wsgiserver

        apps = {'/': _default_app}
        for path, registered_app in _app_register.iteritems():
            apps[path] = registered_app

        d = wsgiserver.WSGIPathInfoDispatcher(apps)
        self.server = wsgiserver.CherryPyWSGIServer((self.bind, self.port), d)

        try:
            host = self.bind if self.bind != "0.0.0.0" else socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            host = '127.0.0.1'

        log.info('Web interface available at http://%s:%s' % (host, self.port))

        self.server.start()

    def run(self):
        self._start_server()

    def stop(self):
        log.info('Shutting down web server')
        if self.server:
            self.server.stop()


@with_session
def do_cli(manager, options, session=None):
    try:
        if hasattr(options, 'user'):
            options.user = options.user.lower()

        if options.action == 'list':
            users = session.query(User).all()
            if users:
                max_width = len(max([user.name for user in users], key=len)) + 4
                console('_' * (max_width + 56 + 9))
                console('| %-*s | %-*s |' % (max_width, 'Username', 56, 'API Token'))
                if users:
                    for user in users:
                        console('| %-*s | %-*s |' % (max_width, user.name, 56, user.token))
            else:
                console('No users found')

        if options.action == 'add':
            exists = session.query(User).filter(User.name == options.user).first()
            if exists:
                console('User %s already exists' % options.user)
                return
            user = User(name=options.user, password=options.password)
            session.add(user)
            session.commit()
            console('Added %s to the database with generated API Token: %s' % (user.name, user.token))

        if options.action == 'delete':
            user = session.query(User).filter(User.name == options.user).first()
            if not user:
                console('User %s does not exist' % options.user)
                return
            session.delete(user)
            session.commit()
            console('Deleted user %s' % options.user)

        if options.action == 'passwd':
            user = session.query(User).filter(User.name == options.user).first()
            if not user:
                console('User %s does not exist' % options.user)
                return

            user.password = options.password
            session.commit()
            console('Updated password for user %s' % options.user)

        if options.action == 'gentoken':
            user = session.query(User).filter(User.name == options.user).first()
            if not user:
                console('User %s does not exist' % options.user)
                return

            user.token = generate_key()
            session.commit()
            console('Generated new token for user %s' % user.name)
            console('Token %s' % user.token)
    finally:
        session.close()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('users', do_cli, help='Manage users providing access to the web server')
    subparsers = parser.add_subparsers(dest='action', metavar='<action>')

    subparsers.add_parser('list', help='List users')

    add_parser = subparsers.add_parser('add', help='add a new user')
    add_parser.add_argument('user', metavar='<username>', help='Users login')
    add_parser.add_argument('password', metavar='<password>', help='Users password')

    del_parser = subparsers.add_parser('delete', help='delete a new user')
    del_parser.add_argument('user', metavar='<username>', help='Login to delete')

    pwd_parser = subparsers.add_parser('passwd', help='change password for user')
    pwd_parser.add_argument('user', metavar='<username>', help='User to change password')
    pwd_parser.add_argument('password', metavar='<new password>', help='New Password')

    gentoken_parser = subparsers.add_parser('gentoken', help='Generate a new api token for a user')
    gentoken_parser.add_argument('user', metavar='<username>', help='User to regenerate api token')
