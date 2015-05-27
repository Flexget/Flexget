from __future__ import unicode_literals, division, absolute_import
import logging
import requests

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('sonarr')

class Sonarr(object):

    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number'},
            'api_key': {'type':'string'}
        },
        'required': ['api_key', 'base_url', 'port'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        url = '%s:%s/api/series' % (config['base_url'], config['port'])
        headers = {'X-Api-Key': config['api_key']}
        json = task.requests.get(url, headers=headers).json()
        entries = []
        for show in json:
            showName = show["title"]
            entry = Entry(title = '%s' % (showName),
                            url = '',
							series_name=(showName))
            if entry.isvalid():
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)

        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(Sonarr, 'sonarr', api_ver=2)
