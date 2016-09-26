from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.api import api_app
from flexget.webserver import get_secret, register_app, setup_server
from flexget.ui import register_web_ui

log = logging.getLogger("web_server_daemon")

web_config_schema = {
    'oneOf': [
        {'type': 'boolean'},
        {'type': 'integer',
         'minimum': 0,
         'maximum': 65536},
        {
            'type': 'object',
            'properties': {
                'bind': {'type': 'string', 'format': 'ipv4'},
                'port': {'type': 'integer',
                         'minimum': 0,
                         'maximum': 65536},
                'ssl_certificate': {'type': 'string'},
                'ssl_private_key': {'type': 'string'},
                'web_ui': {'type': 'boolean'}
            },
            'additionalProperties': False,
            'dependencies': {
                'ssl_certificate': ['ssl_private_key'],
                'ssl_private_key': ['ssl_certificate'],
            }
        }
    ]
}


def prepare_config(config):
    if not config:
        return
    if isinstance(config, bool):
        config = {}
    if isinstance(config, int):
        config = {'port': config}
    config.setdefault('bind', '0.0.0.0')
    config.setdefault('port', 5050)
    config.setdefault('ssl_certificate', None)
    config.setdefault('ssl_private_key', None)
    config.setdefault('web_ui', True)
    return config


@event('config.register')
def register_config():
    register_config_key('web_server', web_config_schema)


@event('manager.daemon.started')
def register_web_server(manager):
    """
    Registers Web Server and loads API (always) and WebUi via config
    """
    web_server_config = manager.config.get('web_server')
    web_server_config = prepare_config(web_server_config)

    if not web_server_config:
        log.debug("Not starting web server as it's disabled or not set in the config")
        return
    log.info("Running web server at IP %s:%s", web_server_config['bind'], web_server_config['port'])
    # Register API
    api_app.secret_key = get_secret()
    log.info("Initiating API")
    register_app('/api', api_app)

    # Register WebUI
    if web_server_config.get('web_ui'):
        log.info('Registering WebUI')
        register_web_ui(manager)

    setup_server(web_server_config)
