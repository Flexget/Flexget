from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import io
import os
import socket

try:
    import mechanicalsoup
except ImportError:
    mechanicalsoup = None
import requests

from flexget import plugin
from flexget.event import event

log = logging.getLogger('formlogin')


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
            'passfield': {'type': 'string'},
        },
        'required': ['url', 'username', 'password'],
        'additionalProperties': False,
    }

    def on_task_start(self, task, config):
        if not mechanicalsoup:
            raise plugin.PluginError(
                'mechanicalsoup required (python module), please install it.', log
            )

        userfield = config.get('userfield', 'username')
        passfield = config.get('passfield', 'password')

        url = config['url']
        username = config['username']
        password = config['password']

        # Mechanicalsoup will override our session user agent header unless we explicitly pass it in
        user_agent = task.requests.headers.get('User-Agent')
        br = mechanicalsoup.StatefulBrowser(session=task.requests, user_agent=user_agent)

        try:
            response = br.open(url)
        except requests.RequestException:
            # TODO: improve error handling
            log.debug('Exception getting login page.', exc_info=True)
            raise plugin.PluginError('Unable to get login page', log)

        # br.set_debug(True)

        num_forms = len(br.get_current_page().find_all('form'))
        if not num_forms:
            raise plugin.PluginError('Unable to find any forms on {}'.format(url), log)
        try:
            for form_num in range(num_forms):
                br.select_form(nr=form_num)
                try:
                    br[userfield] = username
                    br[passfield] = password
                    break
                except mechanicalsoup.LinkNotFoundError:
                    pass
            else:
                received = os.path.join(task.manager.config_base, 'received')
                if not os.path.isdir(received):
                    os.mkdir(received)
                filename = os.path.join(received, '%s.formlogin.html' % task.name)
                with io.open(filename, 'wb') as f:
                    f.write(response.content)
                log.critical('I have saved the login page content to %s for you to view', filename)
                raise plugin.PluginError('Unable to find login fields', log)
        except socket.timeout:
            raise plugin.PluginError('Timed out on url %s' % url)

        try:
            br.submit_selected()
        except requests.RequestException:
            log.debug('Exception submitting login form.', exc_info=True)
            raise plugin.PluginError('Unable to post login form', log)


@event('plugin.register')
def register_plugin():
    plugin.register(FormLogin, 'form', api_ver=2)
