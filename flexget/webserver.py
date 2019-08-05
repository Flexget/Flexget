from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import hashlib
import logging
import random
import socket
import threading

import cherrypy
import zxcvbn
from flask import Flask, abort, redirect
from flask_login import UserMixin
from sqlalchemy import Column, Integer, Unicode
from werkzeug.security import generate_password_hash

from flexget.manager import Base
from flexget.utils.database import with_session

log = logging.getLogger('web_server')

_home = None
_app_register = {}
_default_app = Flask(__name__)

random = random.SystemRandom()


def generate_key():
    """ Generate key for use to authentication """
    return str(hashlib.sha224(str(random.getrandbits(128)).encode('utf-8')).hexdigest())


def get_random_string(
    length=12, allowed_chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
):
    """
    Returns a securely generated random string.

    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits.

    Taken from the django.utils.crypto module.
    """
    return ''.join(random.choice(allowed_chars) for __ in range(length))


@with_session
def get_secret(session=None):
    """ Generate a secret key for flask applications and store it in the database. """
    web_secret = session.query(WebSecret).first()
    if not web_secret:
        web_secret = WebSecret(
            id=1, value=get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')
        )
        session.add(web_secret)
        session.commit()

    return web_secret.value


class WeakPassword(Exception):
    def __init__(self, value, logger=log, **kwargs):
        super(WeakPassword, self).__init__()
        # Value is expected to be a string
        if not isinstance(value, str):
            value = str(value)
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return str(self).encode('utf-8')

    def __unicode__(self):
        return str(self.value)


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


def register_app(path, application):
    if path in _app_register:
        raise ValueError('path %s already registered' % path)
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


def setup_server(config):
    """ Sets up and starts/restarts the web service. """
    web_server = WebServer(
        bind=config['bind'],
        port=config['port'],
        ssl_certificate=config['ssl_certificate'],
        ssl_private_key=config['ssl_private_key'],
        base_url=config['base_url'],
    )

    _default_app.secret_key = get_secret()

    user = get_user()
    if not user or not user.password:
        log.warning(
            'No password set for web server, create one by using'
            ' `flexget web passwd <password>`'
        )

    if _app_register:
        web_server.start()

    return web_server


class WebServer(threading.Thread):
    # We use a regular list for periodic jobs, so you must hold this lock while using it
    triggers_lock = threading.Lock()

    def __init__(
        self, bind='0.0.0.0', port=5050, ssl_certificate=None, ssl_private_key=None, base_url=''
    ):
        threading.Thread.__init__(self, name='web_server')
        self.bind = str(bind)  # String to remove unicode warning from cherrypy startup
        self.port = port
        self.ssl_certificate = ssl_certificate
        self.ssl_private_key = ssl_private_key
        self.base_url = base_url

    def start(self):
        # If we have already started and stopped a thread, we need to reinitialize it to create a new one
        if not self.is_alive():
            self.__init__(
                bind=self.bind,
                port=self.port,
                ssl_certificate=self.ssl_certificate,
                ssl_private_key=self.ssl_private_key,
                base_url=self.base_url,
            )
        threading.Thread.start(self)

    def _start_server(self):
        # Mount the WSGI callable object (app) on the root directory
        cherrypy.tree.graft(_default_app, '/')
        for path, registered_app in _app_register.items():
            cherrypy.tree.graft(registered_app, self.base_url + path)

        cherrypy.log.error_log.propagate = False
        cherrypy.log.access_log.propagate = False

        # Set the configuration of the web server
        cherrypy.config.update(
            {
                'engine.autoreload.on': False,
                'server.socket_port': self.port,
                'server.socket_host': self.bind,
                'log.screen': False,
            }
        )

        if self.ssl_certificate and self.ssl_private_key:
            cherrypy.config.update(
                {
                    'server.ssl_module': 'builtin',
                    'server.ssl_certificate': self.ssl_certificate,
                    'server.ssl_private_key': self.ssl_private_key,
                }
            )

        try:
            host = (
                self.bind if self.bind != "0.0.0.0" else socket.gethostbyname(socket.gethostname())
            )
        except socket.gaierror:
            host = '127.0.0.1'

        protocol = 'https' if self.ssl_certificate and self.ssl_private_key else 'http'

        log.info(
            'Web interface available at %s://%s:%s%s', protocol, host, self.port, self.base_url
        )

        # Start the CherryPy WSGI web server
        cherrypy.engine.start()
        cherrypy.engine.block()

    def run(self):
        self._start_server()

    def stop(self):
        global _app_register

        log.info('Shutting down web server')
        cherrypy.engine.exit()

        # Unregister apps
        _app_register = {}


@with_session
def get_user(username='flexget', session=None):
    user = session.query(User).filter(User.name == username).first()
    if not user:
        user = User()
        user.name = username
        session.add(user)
    return user


@with_session
def change_password(username='flexget', password='', session=None):
    check = zxcvbn.zxcvbn(password, user_inputs=[username])
    if check['score'] < 3:
        warning = check['feedback']['warning']
        suggestions = ' '.join(check['feedback']['suggestions'])
        message = 'Password \'{}\' is not strong enough. '.format(password)
        if warning:
            message += warning + ' '
        if suggestions:
            message += 'Suggestions: {}'.format(suggestions)
        raise WeakPassword(message)

    user = get_user(username=username, session=session)
    user.password = str(generate_password_hash(password))
    session.commit()


@with_session
def generate_token(username='flexget', session=None):
    user = get_user(username=username, session=session)
    user.token = generate_key()
    session.commit()
    return user.token
