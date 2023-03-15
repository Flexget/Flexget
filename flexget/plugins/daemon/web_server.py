from loguru import logger

from flexget.api import api_app
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.ui.v1 import register_web_ui as register_web_ui_v1
from flexget.ui.v2 import register_web_ui as register_web_ui_v2
from flexget.utils.tools import get_config_hash
from flexget.webserver import get_secret, register_app, setup_server

logger = logger.bind(name="web_server_daemon")
config_hash = ''
web_server = None

web_config_schema = {
    'oneOf': [
        {'type': 'boolean'},
        {'type': 'integer', 'minimum': 0, 'maximum': 65536},
        {
            'type': 'object',
            'properties': {
                'bind': {'type': 'string', 'format': 'ipv4'},
                'port': {'type': 'integer', 'minimum': 0, 'maximum': 65536},
                'ssl_certificate': {'type': 'string'},
                'ssl_private_key': {'type': 'string'},
                'web_ui': {'type': 'boolean'},
                'base_url': {'type': 'string'},
                'run_v2': {
                    'type': 'boolean',
                    'deprecated': 'v2 is registered by default if web_ui: true so `run_v2` is now redundant. To run v1 alongside, use the `run_v1`.',
                },
                'run_v1': {'type': 'boolean'},
            },
            'additionalProperties': False,
            'dependencies': {
                'ssl_certificate': ['ssl_private_key'],
                'ssl_private_key': ['ssl_certificate'],
            },
        },
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
    config.setdefault('base_url', '')
    config.setdefault('run_v2', False)
    config.setdefault('run_v1', False)
    if config['base_url']:
        if not config['base_url'].startswith('/'):
            config['base_url'] = '/' + config['base_url']
        if config['base_url'].endswith('/'):
            config['base_url'] = config['base_url'][:-1]

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
        logger.debug('web server config has\'nt changed')
        return

    config_hash = get_config_hash(config)
    web_server_config = prepare_config(config)

    # Removes any existing web server instances if exists
    stop_server(manager)

    if not web_server_config:
        return

    logger.info(
        'Running web server at IP {}:{}', web_server_config['bind'], web_server_config['port']
    )
    # Register API
    api_app.secret_key = get_secret()

    logger.info("Initiating API")
    register_app('/api', api_app, 'API')

    # Register WebUI
    if web_server_config.get('web_ui'):
        if web_server_config.get('run_v1'):
            logger.info('Registering WebUI v1')
            register_web_ui_v1(manager)

        logger.info('Registering WebUI v2')
        register_web_ui_v2(web_server_config)

    web_server = setup_server(web_server_config)


@event('manager.shutdown')
def stop_server(manager):
    """Sets up and starts/restarts the webui."""
    global web_server

    if not manager.is_daemon:
        return

    if web_server and web_server.is_alive():
        web_server.stop()
    web_server = None
