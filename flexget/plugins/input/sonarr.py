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
            'api_key': {'type': 'string'}
        },
        'required': ['api_key', 'base_url', 'port'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        '''
        This plugin returns ALL of the shows monitored by Sonarr.
        This includes both ongoing and ended.
        Syntax:

        sonarr:
          base_url=<value>
          port=<value>
          api_key=<value>

        Use with input plugin like discover and/or cofnigure_series.
        Example:

        download-tv-task:
          configure_series:
            settings:
              quality:
                - 720p
            from:
              sonarr:
                base_url: http://localhost
                port: 8989
                api_key: MYAPIKEY1123
          discover:
            what:
              - emit_series: yes
            from:
              torrentz: any
          download:
            /download/tv

        Note that when using the configure_series plugin with Sonarr
        you are basically synced to it, so removing a show in Sonarr will
        remove it in flexget as well,which good be positive or negative,
        depending on your usage.
        '''
        url = '%s:%s/api/series' % (config['base_url'], config['port'])
        headers = {'X-Api-Key': config['api_key']}
        json = task.requests.get(url, headers=headers).json()
        entries = []
        for show in json:
            entry = Entry(title=show['title'],
                          url='',
                          series_name=show['title'],
                          tvdb_id=show['tvdbId'],
                          tvrage_id=show['tvRageId'])
            if entry.isvalid():
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sonarr, 'sonarr', api_ver=2)
