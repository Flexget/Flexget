from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.api import api_app
from flexget.utils.tools import get_config_hash
from flexget.webserver import get_secret, register_app, setup_server
from flexget.ui import register_web_ui

log = logging.getLogger("web_server_daemon")
config_hash = ''
web_server = None

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


@event('manager.config_updated')
@event('manager.daemon.started')
def register_web_server(manager):
    """Registers Web Server and loads API (always) and WebUi via config"""
    global web_server, config_hash

    if not manager.is_daemon:
        return

    config = manager.config.get('web_server')
    if get_config_hash(config) == config_hash:
        log.debug('web server config has\'nt changed')
        return

    config_hash = get_config_hash(config)
    web_server_config = prepare_config(config)

    # Removes any existing web server instances if exists
    stop_server(manager)

    if not web_server_config:
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

    web_server = setup_server(web_server_config)


@event('manager.shutdown')
def stop_server(manager):
    """ Sets up and starts/restarts the webui. """
    global web_server

    if not manager.is_daemon:
        return

    if web_server and web_server.is_alive():
        web_server.stop()
    web_server = None
