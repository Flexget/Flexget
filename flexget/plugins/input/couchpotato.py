from __future__ import unicode_literals, division, absolute_import
from urlparse import urlparse
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
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'}
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        """Creates an entry for each item in your couchpotato wanted list.

        Syntax:

        couchpotato:
          base_url: <value>
          port: <value>
          api_key: <value>

        Options base_url and api_key are required.
        """
        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/%s/movie.list?status=active' \
              % (parsedurl.scheme, parsedurl.netloc,
                 config.get('port'), parsedurl.path, config.get('api_key'))
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
            # Test mode logging
            if task.options.test: 
                log.info("Test mode. Entry includes:")
                log.info("    Title: %s" % entry["title"])
                log.info("    URL: %s" % entry["url"])
                log.info("    IMDB ID: %s" % entry["imdb_id"])
                log.info("    TMDB ID: %s" % entry["tmdb_id"])
                continue
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(CouchPotato, 'couchpotato', api_ver=2)
