from flexget.event import event
from flexget.config_schema import register_config_key


main_schema = {
    'type': 'object',
    'properties': {
        'bind': {'type': 'string', 'format': 'ipv4', 'default': '0.0.0.0'},
        'port': {'type': 'integer', 'default': 5050},
        'authentication': {
            'oneOf': [
                {"type": "boolean"},
                {
                    "type": "object",
                    "properties": {
                        'username': {'type': 'string'},
                        'password': {'type': 'string'},
                        'no_local_auth': {'type': 'boolean', 'default': True}
                    },
                    'additionalProperties': False
                }
            ]
        }
    },
    'additionalProperties': False
}

@event('config.register')
def register_config():
    register_config_key('webui', main_schema)


@event('manager.daemon.started')
def register_webui(manager):
    webui_config = manager.config.get('api')

    if webui_config:
        # TODO: register webui app
        pass