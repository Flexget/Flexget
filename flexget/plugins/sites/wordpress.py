from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode

import logging

import re
from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning, PluginError
from requests import Session
from requests import Request, RequestException
from requests.utils import dict_from_cookiejar, cookiejar_from_dict

log = logging.getLogger('wordpress_auth')


class WPLoginHeaders(dict):
    def __init__(self, **kwargs):
        super(WPLoginHeaders, self).__init__({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/50.0.2661.102 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'DNT': '1'
        })


class WPLoginData(dict):
    def __init__(self, username='', password='', redirect='/wp-admin/'):
        super(WPLoginData, self).__init__({
            'log': username,
            'pwd': password,
            'wp-submit': 'Log In',
            'testcookie': '1',
            'redirect_to': redirect
        })

    def encode(self):
        return bytes(urlencode(self).encode('UTF-8'))


class WPLoginRequest(Request):
    def __init__(self, url, username='', password=''):
        super(WPLoginRequest, self).__init__(method='POST', url=url, headers=WPLoginHeaders(),
                                             data=WPLoginData(username=username, password=password).encode())


class WPSession(Session):
    def __init__(self):
        super(WPSession, self).__init__()
        self.max_redirects = 5


def _send_request(session, prep_request):
    try:
        response = session.send(prep_request)
    except RequestException as err:
        log.error('%s', err)
        raise PluginError('Issue connecting to %s' % (prep_request.url,))
    if not response.ok:
        log.error('%s', response)
        raise PluginError('Issue connecting to %s: %s' % (prep_request.url, response))
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
        cookies = get_cookies(WPSession(), WPLoginRequest(url, username=username, password=password).prepare())
        task.requests.add_cookiejar(cookiejar_from_dict(cookies))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginWordPress, 'wordpress_auth', api_ver=2)
