import json

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import RequestException

logger = logger.bind(name='kodi_library')

JSON_URI = '/jsonrpc'


class KodiLibrary:
    schema = {
        'type': 'object',
        'properties': {
            'action': {'type': 'string', 'enum': ['clean', 'scan']},
            'category': {'type': 'string', 'enum': ['audio', 'video']},
            'url': {'type': 'string', 'format': 'url'},
            'port': {'type': 'integer', 'default': 8080},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'only_on_accepted': {'type': 'boolean', 'default': True},
        },
        'required': ['url', 'action', 'category'],
        'additionalProperties': False,
    }

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_exit(self, task, config):
        if task.accepted or not config['only_on_accepted']:
            # make the url without trailing slash
            base_url = config['url'][:-1] if config['url'].endswith('/') else config['url']
            base_url += ':{0}'.format(config['port'])

            url = base_url + JSON_URI
            # create the params
            params = {
                "id": 1,
                "jsonrpc": "2.0",
                'method': '{category}Library.{action}'.format(
                    category=config['category'].title(), action=config['action'].title()
                ),
            }
            logger.debug('Sending request params {}', params)

            try:
                r = task.requests.post(
                    url, json=params, auth=(config.get('username'), config.get('password'))
                ).json()
                if r.get('result') == 'OK':
                    logger.info(
                        'Successfully sent a {} request for the {} library',
                        config['action'],
                        config['category'],
                    )
                else:
                    if r.get('error'):
                        logger.error(
                            'Kodi JSONRPC failed. Error {}: {}',
                            r['error']['code'],
                            r['error']['message'],
                        )
                    else:
                        # this should never happen as Kodi say they follow the JSON-RPC 2.0 spec
                        logger.debug('Received error response {}', json.dumps(r))
                        logger.error(
                            'Kodi JSONRPC failed with unrecognized message: {}', json.dumps(r)
                        )
            except RequestException as e:
                raise plugin.PluginError('Failed to send request to Kodi: %s' % e.args[0])
        else:
            logger.info('No entries were accepted. No request is sent.')


@event('plugin.register')
def register_plugin():
    plugin.register(KodiLibrary, 'kodi_library', api_ver=2)
