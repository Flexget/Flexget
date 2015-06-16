from __future__ import unicode_literals, division, absolute_import
from urlparse import urlparse
import logging

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('sickbeard')


class Sickbeard(object):

    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_ended': {'type': 'boolean', 'default': True},
            'only_monitored': {'type': 'boolean', 'default': False},
            'include_data': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url'],
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

        Options base_url and api_key are required.

        Use with input plugin like discover and/or configure_series.
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
        remove it in flexget as well, which could be positive or negative,
        depending on your usage.
        '''
        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/%s/?cmd=shows' % (parsedurl.scheme, parsedurl.netloc,
                                                  config.get('port'), parsedurl.path, config.get('api_key'))
        json = task.requests.get(url).json()
        entries = []
        # Dictionary based on SB quality list.
        qualities = {'Any': '',
                     'HD': '720p-1080p',
                     'HD1080p': '1080p',
                     'HD720p': '720p',
                     'SD': '<hr'}
        for id, show in json['data'].items():
            fg_quality = '' # Initializes the quality parameter
            show_path='' # Initializes the path parameter
            if not show['paused'] or not config.get('only_monitored'): 
                if config.get('include_ended') or show['status'] != 'Ended':
                    if config.get('include_data'):
                        show_url ='%s:%s/api/%s/?cmd=show&tvdbid=%s' % (config['base_url'], config['port'], config['api_key'], show['tvdbid'])
                        show_json = task.requests.get(show_url).json()
                        sb_quality = show_json['data']['quality']
                        fg_quality = qualities[sb_quality]
                        show_path = show_json['data']['location']
                    entry = Entry(title=show['show_name'],
                                  url='',
                                  series_name=show['show_name'],
                                  tvdb_id=show['tvdbid'],
                                  tvrage_id=show['tvrage_id'],
                                  # configure_series plugin requires that all settings will have the configure_series prefix
                                  configure_series_quality=fg_quality,
                                  configure_series_path=show_path)
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
                log.info("    Quality: %s" % entry["configure_series_quality"])
                log.info("    Path: %s" % entry["configure_series_path"])
                continue
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sickbeard, 'sickbeard', api_ver=2)
