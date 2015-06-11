from __future__ import unicode_literals, division, absolute_import
from urlparse import urlparse
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
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_ended': {'type': 'boolean', 'default': True},
            'only_monitored': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url'],
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
          include_ended=<yes|no>
          only_monitored=<yes|no>

        Options base_url and api_key are required.

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
        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/series' % (parsedurl.scheme, parsedurl.netloc, config.get('port'), parsedurl.path)
        headers = {'X-Api-Key': config['api_key']}
        json = task.requests.get(url, headers=headers).json()
        entries = []
        for show in json:
            if show['monitored'] or not config.get('only_monitored'):
                if config.get('include_ended') or show['status'] != 'ended':
                    entry = Entry(title=show['title'],
                                  url='',
                                  series_name=show['title'],
                                  tvdb_id=show['tvdbId'],
                                  tvrage_id=show['tvRageId'])
                    if entry.isvalid():
                        entries.append(entry)
                    else:
                        log.debug('Invalid entry created? %s' % entry)
            # Test mode logging
            if task.options.test: 
                log.info("Test mode. Entry includes:")
                log.info("    Title: %s" % entry["title"])
                log.info("    URL: %s" % entry["url"])
                log.info("    Show name: %s" % entry["series_name"])
                log.info("    TVDB ID: %s" % entry["tvdb_id"])
                log.info("    TVRAGE ID: %s" % entry["tvrage_id"])
                continue
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sonarr, 'sonarr', api_ver=2)
