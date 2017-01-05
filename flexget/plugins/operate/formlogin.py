from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import io
import os
import socket

try:
    import mechanize
except ImportError:
    mechanize = None

from flexget import plugin
from flexget.event import event
from flexget.utils.soup import get_soup

log = logging.getLogger('formlogin')


if mechanize:
    class SanitizeHandler(mechanize.BaseHandler):
        def http_response(self, request, response):
            if not hasattr(response, "seek"):
                response = mechanize.response_seek_wrapper(response)
            # Run HTML through BeautifulSoup for sanitizing
            if 'html' in response.info().get('content-type', ''):
                soup = get_soup(response.get_data())
                response.set_data(soup.prettify(encoding=soup.original_encoding))
            return response


class FormLogin(object):
    """
    Login on form
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'userfield': {'type': 'string'},
            'passfield': {'type': 'string'}
        },
        'required': ['url', 'username', 'password'],
        'additionalProperties': False
    }

    def on_task_start(self, task, config):
        if not mechanize:
            raise plugin.PluginError('mechanize required (python module), please install it.', log)

        userfield = config.get('userfield', 'username')
        passfield = config.get('passfield', 'password')

        url = config['url']
        username = config['username']
        password = config['password']

        br = mechanize.Browser()
        br.add_handler(SanitizeHandler())
        br.set_handle_robots(False)
        try:
            br.open(url)
        except Exception:
            # TODO: improve error handling
            log.debug('Exception posting login form.', exc_info=True)
            raise plugin.PluginError('Unable to post login form', log)

        # br.set_debug_redirects(True)
        # br.set_debug_responses(True)
        # br.set_debug_http(True)

        try:
            for form in br.forms():
                loginform = form

                try:
                    loginform[userfield] = username
                    loginform[passfield] = password
                    break
                except Exception:
                    pass
            else:
                received = os.path.join(task.manager.config_base, 'received')
                if not os.path.isdir(received):
                    os.mkdir(received)
                filename = os.path.join(received, '%s.formlogin.html' % task.name)
                with io.open(filename, 'wb') as f:
                    f.write(br.response().get_data())
                log.critical('I have saved the login page content to %s for you to view', filename)
                raise plugin.PluginError('Unable to find login fields', log)
        except socket.timeout:
            raise plugin.PluginError('Timed out on url %s' % url)

        br.form = loginform

        br.submit()

        cookiejar = br._ua_handlers["_cookies"].cookiejar

        # Add cookiejar to our requests session
        task.requests.add_cookiejar(cookiejar)


@event('plugin.register')
def register_plugin():
    plugin.register(FormLogin, 'form', api_ver=2)
