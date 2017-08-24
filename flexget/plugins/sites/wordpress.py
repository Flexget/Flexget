from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning, PluginError
from requests import Session
from requests import Request, RequestException
from requests.utils import dict_from_cookiejar

log = logging.getLogger('wordpress_auth')


class WPLoginException(Exception):
    def __init__(self, message=''):
        self._message = message

    def __str__(self):
        return self._message


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


def get_auth(session, prep_request):
    try:
        res = session.send(prep_request)
    except RequestException as err:
        log.error('%s', err)
        raise WPLoginException('Issue connecting to %s:' % (prep_request.url,))
    if not res.ok:
        log.error('%s', res)
        raise WPLoginException('Issue connecting to %s: %s' % (prep_request.url, res))

    cookies = dict_from_cookiejar(res.cookies)
    for h_res in res.history:
        cookies.update(dict_from_cookiejar(h_res.cookies))

    return cookies


class PluginWordpress(object):
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
            get_auth(WPSession(), WPLoginRequest(url, username=username, password=password).prepare())
        except WPLoginException as err:
            raise PluginError(str(err))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginWordpress, 'wordpress_auth', api_ver=2)
