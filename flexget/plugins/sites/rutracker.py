# coding=utf-8
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json
import logging
from time import sleep
from datetime import datetime, timedelta

from sqlalchemy import Column, Unicode, Integer, DateTime
from sqlalchemy.types import TypeDecorator, VARCHAR

import re
from flexget import plugin
from flexget.event import event
from flexget.db_schema import versioned_base
from flexget.plugin import PluginError
from flexget.manager import Session
from requests import Session as RSession
from requests.auth import AuthBase
from requests.utils import dict_from_cookiejar
from requests.exceptions import RequestException

__author__ = 'asm0dey'

log = logging.getLogger('rutracker_auth')
Base = versioned_base('rutracker_auth', 0)

MIRRORS = ['https://rutracker.cr',
           'https://rutracker.net',
           'https://rutracker.org']


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string.

    Usage:

        JSONEncodedDict(255)

    """

    impl = VARCHAR

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)

        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class RutrackerAccount(Base):
    __tablename__ = 'rutracker_accoounts'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    login = Column(Unicode, index=True)
    cookies = Column(JSONEncodedDict)
    expiry_time = Column(DateTime)


class RutrackerAuth(AuthBase):
    """Supports downloading of torrents from 'rutracker' tracker
       if you pass cookies (CookieJar) to constructor then authentication will be bypassed and cookies will be just set
    """

    @staticmethod
    def update_base_url():
        url = None
        for mirror in MIRRORS:
            try:
                s = RSession()
                response = s.get(mirror, timeout=2)
                if response.ok:
                    url = mirror
                    break
            except RequestException as err:
                log.debug('Connection error. %s', str(err))

        if url:
            return url
        else:
            raise PluginError('Host unreachable.')

    def try_authenticate(self, payload):
        for _ in range(5):
            s = RSession()
            s.post('{}/forum/login.php'.format(self.base_url), data=payload)
            if s.cookies and len(s.cookies) > 0:
                return s.cookies
            else:
                sleep(3)
        raise PluginError('unable to obtain cookies from rutracker')

    def __init__(self, login, password, cookies=None, db_session=None):
        self.base_url = self.update_base_url()
        if cookies is None:
            log.debug('rutracker cookie not found. Requesting new one')
            payload_ = {'login_username': login,
                        'login_password': password, 'login': 'Вход'}
            self.cookies_ = self.try_authenticate(payload_)
            if db_session:
                db_session.add(
                    RutrackerAccount(
                        login=login, cookies=dict_from_cookiejar(
                            self.cookies_),
                        expiry_time=datetime.now() + timedelta(days=1)))
                db_session.commit()
            else:
                raise ValueError(
                    'db_session can not be None if cookies is None')
        else:
            log.debug('Using previously saved cookie')
            self.cookies_ = cookies

    def __call__(self, r):
        url = r.url
        t_id = re.findall(r'\d+', url)[0]
        data = 't={}'.format(t_id)
        headers = {
            'referer': '{}/forum/viewtopic.php?t={}'.format(self.base_url, t_id),
            'Content-Type': 'application/x-www-form-urlencoded', 't': t_id,
            'Origin': self.base_url,
            'Accept-Encoding': 'gzip,deflate,sdch'}
        r.prepare_body(data=data, files=None)
        r.prepare_method('POST')
        r.prepare_url(url='{}/forum/dl.php?t={}'.format(self.base_url, t_id), params=None)
        r.prepare_headers(headers)
        r.prepare_cookies(self.cookies_)
        return r


class RutrackerUrlrewrite(object):
    """Usage:

    rutracker_auth:
      username: 'username_here'
      password: 'password_here'
    """
    schema = {'type': 'object',
              'properties': {
                  'username': {'type': 'string'},
                  'password': {'type': 'string'}
              },
              'additionalProperties': False}

    auth_cache = {}

    @plugin.priority(127)
    def on_task_urlrewrite(self, task, config):
        username = config['username']
        db_session = Session()
        cookies = self.try_find_cookie(db_session, username)
        if username not in self.auth_cache:
            auth_handler = RutrackerAuth(
                username, config['password'], cookies, db_session)
            self.auth_cache[username] = auth_handler
        else:
            auth_handler = self.auth_cache[username]
        for entry in task.accepted:
            if re.match('https?:\/\/rutracker', entry['url']):
                entry['download_auth'] = auth_handler

    @staticmethod
    def try_find_cookie(db_session, username):
        account = db_session.query(RutrackerAccount).filter(
            RutrackerAccount.login == username).first()
        if account:
            if account.expiry_time < datetime.now():
                db_session.delete(account)
                db_session.commit()
                return None
            return account.cookies
        else:
            return None


@event('plugin.register')
def register_plugin():
    plugin.register(RutrackerUrlrewrite, 'rutracker_auth', api_ver=2)
