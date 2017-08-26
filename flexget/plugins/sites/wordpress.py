from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode

import logging

import re
from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError
from requests import Request, RequestException
from requests.utils import dict_from_cookiejar, cookiejar_from_dict

log = logging.getLogger('wordpress_auth')


def construct_wp_login_request(url, username='', password='', redirect='/wp-admin/'):
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


def match_wordpress_cookie(key):
    return re.match(r'wordpress(?!_test)[A-z0-9]*', key, re.IGNORECASE)


def collect_cookies_from_response(response):
    cookies = dict_from_cookiejar(response.cookies)
    for h_resp in response.history:
        cookies.update(dict_from_cookiejar(h_resp.cookies))
    return cookies


def validate_cookies(cookies, matcher):
    cnt_matches = sum([1 for key in cookies.keys() if matcher(key)])
    if cnt_matches < 1:
        log.warning('No recognized WordPress cookies found. Perhaps username/password is invalid?')


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
        try:
            response = task.requests.send(construct_wp_login_request(url, username=username, password=password))
            if not response.ok:
                log.error('%s', response)
                raise PluginError('Issue connecting to %s: %s' % (url, response))
            cookies = collect_cookies_from_response(response)
            validate_cookies(cookies, match_wordpress_cookie)
            task.requests.add_cookiejar(cookiejar_from_dict(cookies))
        except RequestException as err:
            log.error('%s', err)
            raise PluginError('Issue connecting to %s' % (url,))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginWordPress, 'wordpress_auth', api_ver=2)
