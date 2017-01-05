from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse

import logging

from requests import RequestException

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

    def quality_requirement_builder(self, quality_list):
        """
        Translates sickbeards' qualities into format used by Flexget
        """
        sb_to_fg = {'sdtv': 'sdtv',
                    'sddvd': 'dvdrip',
                    'hdtv': '720p hdtv',
                    'rawhdtv': '1080p hdtv',
                    'fullhdtv': '1080p hdtv',
                    'hdwebdl': '720p webdl',
                    'fullhdwebdl': '1080p webdl',
                    'hdbluray': '720p bluray',
                    'fullhdbluray': '1080p bluray',
                    'unknown': 'any'}

        return [sb_to_fg[quality] for quality in quality_list]

    def on_task_input(self, task, config):
        """
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
              - next_series_episodes: yes
            from:
              torrentz: any
          download:
            /download/tv

        Note that when using the configure_series plugin with Sickbeard
        you are basically synced to it, so removing a show in Sickbeard will
        remove it in flexget as well, which could be positive or negative,
        depending on your usage.
        """
        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/%s/?cmd=shows' % (parsedurl.scheme, parsedurl.netloc,
                                                  config.get('port'), parsedurl.path, config.get('api_key'))
        try:
            json = task.requests.get(url).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sickbeard at %s://%s:%s%s. Error: %s'
                                     % (parsedurl.scheme, parsedurl.netloc, config.get('port'), parsedurl.path, e))
        entries = []
        for _, show in list(json['data'].items()):
            log.debug('processing show: {}'.format(show))
            fg_qualities = ''  # Initializes the quality parameter
            if show['paused'] and config.get('only_monitored'):
                continue
            if show['status'] == 'Ended' and not config.get('include_ended'):
                continue
            if config.get('include_data'):
                show_url = '%s:%s/api/%s/?cmd=show&tvdbid=%s' % (config['base_url'], config['port'],
                                                                 config['api_key'], show['tvdbid'])
                show_json = task.requests.get(show_url).json()
                log.deubg('processing show data: {}'.format(show_json['data']))
                fg_qualities = self.quality_requirement_builder(show_json['data']['quality_details']['initial'])
            entry = Entry(title=show['show_name'],
                          url='',
                          series_name=show['show_name'],
                          tvdb_id=show.get('tvdbid'),
                          tvrage_id=show.get('tvrage_id'))
            if len(fg_qualities) > 1:
                entry['configure_series_qualities'] = fg_qualities
            elif len(fg_qualities) == 1:
                entry['configure_series_quality'] = fg_qualities[0]
            else:
                entry['configure_series_quality'] = fg_qualities
            if entry.isvalid():
                entries.append(entry)
            else:
                log.error('Invalid entry created? %s' % entry)
                continue
            # Test mode logging
            if task.options.test:
                log.info("Test mode. Entry includes:")
                for key, value in list(entry.items()):
                    log.info('     {}: {}'.format(key.capitalize(), value))

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sickbeard, 'sickbeard', api_ver=2)
