from __future__ import absolute_import, division, unicode_literals

from urlparse import urljoin

from requests import Session#TODO: Switch to flexget session?

from flexget import plugin
from flexget.utils import json
from flexget.utils.requests import RequestException#TODO: , Session


API_KEY = '980c477226b9c18c9a4982cddc1bdbcd747d14b006fe044a8bbbe29bfb640b5d'
API_URL = 'http://api.v2.trakt.tv/'


def make_list_slug(name):
    """Return the slug for use in url for given list name."""
    slug = name.lower()
    # These characters are just stripped in the url
    for char in '!@#$%^*()[]{}/=?+\\|-_':
        slug = slug.replace(char, '')
    # These characters get replaced
    slug = slug.replace('&', 'and')
    slug = slug.replace(' ', '-')
    return slug


def get_session(username=None, password=None):
    session = Session()
    session.headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': 2,
        'trakt-api-key': API_KEY
    }
    if username:
        session.headers['trakt-user-login'] = username
    if username and password:
        auth = {'login': username, 'password': password}
        try:
            r = session.post(urljoin(API_URL, 'auth/login'), data=json.dumps(auth))
        except RequestException as e:
            raise plugin.PluginError('Authentication to trakt failed, check your username/password: %s' % e.args[0])
        try:
            session.headers['trakt-user-token'] = r.json()['token']
        except (ValueError, KeyError):
            raise plugin.PluginError('Got unexpected response content while authorizing to trakt: %s' % r.text)
    return session