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


def construct_request(url, username='', password='', redirect='/wp-admin/'):
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


def collect_cookies(response):
    cookies = dict_from_cookiejar(response.cookies)
    for h_resp in response.history:
        cookies.update(dict_from_cookiejar(h_resp.cookies))
    return cookiejar_from_dict(cookies)


def get_valid_cookies(cookies):
    def is_wp_cookie(key):
        return re.match(r'(wordpress|wp)(?!_*test)[A-z0-9]*', key, re.IGNORECASE)

    valid_cookies = {key: value for key, value in cookies.items() if is_wp_cookie(key)}
    return cookiejar_from_dict(valid_cookies)


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
            response = task.requests.send(construct_request(url, username=username, password=password))
            if not response.ok:
                raise RequestException(str(response))
            cookies = collect_cookies(response)
            if len(get_valid_cookies(cookies)) < 1:
                raise RequestException('No recognized WordPress cookies found. Perhaps username/password is invalid?')
            task.requests.add_cookiejar(cookies)

        except RequestException as err:
            log.error('%s', err)
            raise PluginError('WordPress Authentication at %s failed' % (url,))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginWordPress, 'wordpress_auth', api_ver=2)
