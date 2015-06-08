from __future__ import unicode_literals, division, absolute_import
import logging
import requests

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('couchpotato')


class CouchPotato(object):

    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'tpye': 'string'},
            'port': {'type': 'number'},
            'api_key': {'type': 'string'}
        },
        'required': ['api_key', 'base_url', 'port'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        """Creates an entry for each item in your couchpotato wanted list.

        Syntax:

        couchpotato:
          base_url: <value>
          port: <value>
          api_key: <value>

        Options base_url, port and api_key are required.
        """

        url = '%s:%s/api/%s/movie.list?status=active' \
              % (config['base_url'], config['port'], config['api_key'])
        json = task.requests.get(url).json()
        entries = []
        for movie in json['movies']:
            if movie['status'] == 'active':
                title = movie["title"]
                imdb = movie['info']['imdb']
                tmdb = movie['info']['tmdb_id']
                entry = Entry(title=title,
                              url='',
                              imdb_id=imdb,
                              tmdb_id=tmdb)
                if entry.isvalid():
                    entries.append(entry)
                else:
                    log.debug('Invalid entry created? %s' % entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(CouchPotato, 'couchpotato', api_ver=2)
