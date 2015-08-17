"""
Utilities to use api v2 api.

TODO: This should probably all be moved to api_trakt.py once that is converted to api v2
"""

from __future__ import absolute_import, division, unicode_literals

from urlparse import urljoin

from flexget import plugin
from flexget.utils import json
from requests.exceptions import Timeout
from flexget.utils.requests import RequestException, Session


# Testing site
# API_KEY = '980c477226b9c18c9a4982cddc1bdbcd747d14b006fe044a8bbbe29bfb640b5d'
# API_URL = 'http://api.staging.trakt.tv/'
# Production Site
API_KEY = '57e188bcb9750c79ed452e1674925bc6848bd126e02bb15350211be74c6547af'
# API_URL = 'https://api.trakt.tv/'
API_URL = 'https://api-v2launch.trakt.tv/'


def make_list_slug(name):
    """Return the slug for use in url for given list name."""
    slug = name.lower()
    # These characters are just stripped in the url
    for char in '!@#$%^*()[]{}/=?+\\|':
        slug = slug.replace(char, '')
    # These characters get replaced
    slug = slug.replace('&', 'and')
    slug = slug.replace(' ', '-')
    return slug


def get_session(username=None, password=None):
    """Creates a requests session which is authenticated to trakt."""
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
        except Timeout:  # requests.exceptions.Timeout
            raise plugin.PluginError('Authentication timed out to trakt')
        except RequestException as e:
            if hasattr(e, 'response') and e.response.status_code in [401, 403]:
                raise plugin.PluginError('Authentication to trakt failed, check your username/password: %s' % e.args[0])
            else:
                raise plugin.PluginError('Authentication to trakt failed: %s' % e.args[0])
        try:
            session.headers['trakt-user-token'] = r.json()['token']
        except (ValueError, KeyError):
            raise plugin.PluginError('Got unexpected response content while authorizing to trakt: %s' % r.text)
    return session


def get_api_url(*endpoint):
    """
    Get the address of a trakt API endpoint.

    :param endpoint: Can by a string endpoint (e.g. 'sync/watchlist') or an iterable (e.g. ('sync', 'watchlist')
        Multiple parameters can also be specified instead of a single iterable.
    :returns: The absolute url to the specified API endpoint.
    """
    if len(endpoint) == 1 and not isinstance(endpoint[0], basestring):
        endpoint = endpoint[0]
    # Make sure integer portions are turned into strings first too
    url = API_URL + '/'.join(map(unicode, endpoint))
    return url


def get_entry_ids(entry):
    """Creates a trakt ids dict from id fields on an entry. Prefers already populated info over lazy lookups."""
    ids = {}
    for lazy in [False, True]:
        if entry.get('trakt_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_id']
        if entry.get('tmdb_id', eval_lazy=lazy):
            ids['tmdb'] = entry['tmdb_id']
        if entry.get('tvdb_id', eval_lazy=lazy):
            ids['tvdb'] = entry['tvdb_id']
        if entry.get('imdb_id', eval_lazy=lazy):
            ids['imdb'] = entry['imdb_id']
        if entry.get('tvrage_id', eval_lazy=lazy):
            ids['tvrage'] = entry['tvrage_id']
        if ids:
            break
    return ids
