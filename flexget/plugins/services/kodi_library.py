from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import json

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import RequestException

log = logging.getLogger('kodi_library')

JSON_URI = '/jsonrpc'


class KodiLibrary(object):
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
            log.debug('Sending request params %s', params)

            try:
                r = task.requests.post(
                    url, json=params, auth=(config.get('username'), config.get('password'))
                ).json()
                if r.get('result') == 'OK':
                    log.info(
                        'Successfully sent a %s request for the %s library',
                        config['action'],
                        config['category'],
                    )
                else:
                    if r.get('error'):
                        log.error(
                            'Kodi JSONRPC failed. Error %s: %s',
                            r['error']['code'],
                            r['error']['message'],
                        )
                    else:
                        # this should never happen as Kodi say they follow the JSON-RPC 2.0 spec
                        log.debug('Received error response %s', json.dumps(r))
                        log.error(
                            'Kodi JSONRPC failed with unrecognized message: %s', json.dumps(r)
                        )
            except RequestException as e:
                raise plugin.PluginError('Failed to send request to Kodi: %s' % e.args[0])
        else:
            log.info('No entries were accepted. No request is sent.')


@event('plugin.register')
def register_plugin():
    plugin.register(KodiLibrary, 'kodi_library', api_ver=2)
