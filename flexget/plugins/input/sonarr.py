from __future__ import unicode_literals, division, absolute_import
from urlparse import urlparse
import logging
from requests import RequestException

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
            'only_monitored': {'type': 'boolean', 'default': True},
            'include_data': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        """
        This plugin returns ALL of the shows monitored by Sonarr.
        Return ended shows by default and does not return unmonitored
        show by default.

        Syntax:

        sonarr:
          base_url=<value>
          port=<value>
          api_key=<value>
          include_ended=<yes|no>
          only_monitored=<yes|no>
          include_data=<yes|no>

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
        """
        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/series' % (parsedurl.scheme, parsedurl.netloc, config.get('port'), parsedurl.path)
        headers = {'X-Api-Key': config['api_key']}
        try:
            json = task.requests.get(url, headers=headers).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sonarr at %s://%s:%s%s. Error: %s'
                                     % (parsedurl.scheme, parsedurl.netloc, config.get('port'),
                                        parsedurl.path, e))
        entries = []
        # Dictionary based on Sonarr's quality list.
        qualities = {0: '',
                     1: 'sdtv',
                     2: 'dvdrip',
                     3: '1080p webdl',
                     4: '720p hdtv',
                     5: '720p webdl',
                     6: '720p bluray',
                     7: '1080p bluray',
                     8: '480p webdl',
                     9: '1080p hdtv',
                     10: '1080p bluray'}
        # Retrieves Sonarr's profile list if include_data is set to true
        if config.get('include_data'):  
            url2 = '%s://%s:%s%s/api/profile' % (parsedurl.scheme, parsedurl.netloc, config.get('port'), parsedurl.path)
            try:
                profiles_json = task.requests.get(url2, headers=headers).json()
            except RequestException as e:
                raise plugin.PluginError('Unable to connect to Sonarr at %s://%s:%s%s. Error: %s'
                                         % (parsedurl.scheme, parsedurl.netloc, config.get('port'),
                                            parsedurl.path, e))
        for show in json:
            fg_quality = ''  # Initializes the quality parameter
            entry = None
            if show['monitored'] or not config.get('only_monitored'):  # Checks if to retrieve just monitored shows
                if config.get('include_ended') or show['status'] != 'ended':  # Checks if to retrieve ended shows
                    if config.get('include_data'):  # Check if to retrieve quality & path
                        for profile in profiles_json:
                            if profile['id'] == show['profileId']:  # Get show's profile data from all possible profiles
                                current_profile = profile    
                        fg_quality = qualities[current_profile['cutoff']['id']]  # Sets profile cutoff quality as show's quality
                    entry = Entry(title=show['title'],
                                  url='',
                                  series_name=show['title'],
                                  tvdb_id=show.get('tvdbId'),
                                  tvrage_id=show.get('tvRageId'),
                                  # configure_series plugin requires that all settings will have the configure_series prefix
                                  configure_series_quality=fg_quality)
                    if entry.isvalid():
                        entries.append(entry)
                    else:
                        log.error('Invalid entry created? %s' % entry)
            # Test mode logging
            if entry and task.options.test:
                log.info("Test mode. Entry includes:")
                log.info("    Title: %s" % entry["title"])
                log.info("    URL: %s" % entry["url"])
                log.info("    Show name: %s" % entry["series_name"])
                log.info("    TVDB ID: %s" % entry["tvdb_id"])
                log.info("    TVRAGE ID: %s" % entry["tvrage_id"])
                log.info("    Quality: %s" % entry["configure_series_quality"])
            # continue
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sonarr, 'sonarr', api_ver=2)
