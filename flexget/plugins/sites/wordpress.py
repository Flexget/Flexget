from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode

import logging

import re
from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError
from requests import Session
from requests import Request, RequestException
from requests.utils import dict_from_cookiejar, cookiejar_from_dict

log = logging.getLogger('wordpress_auth')


def get_wp_login_request(url, username='', password='', redirect='/wp-admin/'):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/50.0.2661.102 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'DNT': '1'
    }
    data = {
        'log': username,
        'pwd': password,
        'wp-submit': 'Log In',
        'testcookie': '1',
        'redirect_to': redirect
    }
    return Request(method='POST', url=url, headers=headers, data=urlencode(data).encode('UTF-8')).prepare()


def get_wp_login_session(redirects=5):
    s = Session()
    s.max_redirects = redirects
    return s


def _send_request(session, prep_request):
    try:
        response = session.send(prep_request)
    except RequestException as err:
        log.error('%s', err)
        session.close()
        raise PluginError('Issue connecting to %s' % (prep_request.url,))
    if not response.ok:
        log.error('%s', response)
        session.close()
        raise PluginError('Issue connecting to %s: %s' % (prep_request.url, response))
    session.close()
    return response


def _collect_cookies_from_response(response):
    cookies = dict_from_cookiejar(response.cookies)
    for h_resp in response.history:
        cookies.update(dict_from_cookiejar(h_resp.cookies))
    return cookies


def _match_valid_wordpress_cookies(cookies):
    def match(key):
        return re.match(r'wordpress(?!_test)[A-z0-9]*', key, re.IGNORECASE)

    return [{key, value} for key, value in cookies.items() if match(key)]


def _validate_cookies(cookies):
    matches = _match_valid_wordpress_cookies(cookies)
    if len(matches) < 1:
        log.warning('No recognized WordPress cookies found. Perhaps username/password is invalid?')


def get_cookies(session, prep_request):
    resp = _send_request(session, prep_request)
    cookies = _collect_cookies_from_response(resp)
    _validate_cookies(cookies)
    return cookies


class PluginWordPress(object):
    """
    Supports accessing feeds and media that require wordpress account credentials
    Usage:

    wordpress_auth:
      url: 'your wordpress blog login page (ex http://example.org/wp-login.php)'
      username: 'your username'
      password: 'your password'
    """

    schema = {'type': 'object',
              'properties': {
                  'url': {'type': 'string', 'oneOf': [{'format': 'url'}]},
                  'username': {'type': 'string', 'default': ''},
                  'password': {'type': 'string', 'default': ''}
              },
              'required': ['url'],
              'additionalProperties': False
              }

    @plugin.priority(135)
    def on_task_start(self, task, config):
        url = config['url']
        username = config['username']
        password = config['password']
        cookies = get_cookies(get_wp_login_session(), get_wp_login_request(url, username=username, password=password))
        task.requests.add_cookiejar(cookiejar_from_dict(cookies))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginWordPress, 'wordpress_auth', api_ver=2)
