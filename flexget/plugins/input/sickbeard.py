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
        '''
        This plugin returns ALL of the shows monitored by Sickbeard.
        This includes both ongoing and ended.
        Syntax:

        sickbeard:
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
              sickbeard:
                base_url: http://localhost
                port: 8531
                api_key: MYAPIKEY1123
          discover:
            what:
              - emit_series: yes
            from:
              torrentz: any
          download:
            /download/tv

        Note that when using the configure_series plugin with Sickbeard
        you are basically synced to it, so removing a show in Sickbeard will
        remove it in flexget as well,which good be positive or negative,
        depending on your usage.
        '''
        url = '%s:%s/api/%s/?cmd=shows' % (config['base_url'], config['port'], config['api_key'])
        json = task.requests.get(url).json()
        entries = []
        for id, show in json['data'].items():
            entry = Entry(title=show['show_name'],
                          url='',
                          series_name=show['show_name'],
                          tvdb_id=show['tvdbid'],
                          tvrage_id=show['tvrage_id'])
            if entry.isvalid():
                entries.append(entry)
            else:
                log.debug('Invalid entry created? %s' % entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sickbeard, 'sickbeard', api_ver=2)
