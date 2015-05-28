from __future__ import unicode_literals, division, absolute_import
import logging
import requests

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('sickbeard')


class Sickbeard(object):

    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number'},
            'api_key': {'type': 'string'}
        },
        'required': ['api_key', 'base_url', 'port'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        url = '%s:%s/api/%s/?cmd=shows' % (config['base_url'], config['port'], config['api_key'])
        json = task.requests.get(url).json()
        entries = []
        for id, show in json['data'].items():
            entry = Entry(title=show['show_name'],
                          url='',
                          series_name=show['show_name'],
						  tvdb_id=show['tvdbid'].
						  tvrage_id=show['tvrage_id'])
            if entry.isvalid():
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sickbeard, 'sickbeard', api_ver=2)
