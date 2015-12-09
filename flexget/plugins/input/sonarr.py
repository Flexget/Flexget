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

    def transalte_quality(self, quality_name):
        """
        Translate Sonnar's qualities to ones recognize by Flexget
        """
        if quality_name == 'Raw-HD':  # No better match yet in Flexget
            return 'remux'
        elif quality_name == 'DVD':  # No better match yet in Flexget
            return 'dvdrip'
        else:
            return quality_name.replace('-', ' ').lower()

    def quality_requirement_builder(self, quality_profile):

        allowed_qualities = [self.transalte_quality(quality['quality']['name']) for quality in quality_profile['items']
                             if quality['allowed']]
        cutoff = self.transalte_quality(quality_profile['cutoff']['name'])

        return allowed_qualities, cutoff

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

        Use with input plugin like discover and/or configure_series.
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
            fg_qualities = ''  # Initializes the quality parameter
            fg_cutoff = ''
            path = None
            if not show['monitored'] and config.get('only_monitored'):  # Checks if to retrieve just monitored shows
                continue
            if show['status'] == 'ended' and not config.get('include_ended'):  # Checks if to retrieve ended shows
                continue
            if config.get('include_data') and profiles_json:  # Check if to retrieve quality & path
                path = show.get('path')
                for profile in profiles_json:
                    if profile['id'] == show['profileId']:  # Get show's profile data from all possible profiles
                        fg_qualities, fg_cutoff = self.quality_requirement_builder(profile)
            entry = Entry(title=show['title'],
                          url='',
                          series_name=show['title'],
                          tvdb_id=show.get('tvdbId'),
                          tvrage_id=show.get('tvRageId'),
                          tvmaze_id=show.get('tvMazeId'),
                          configure_series_target=fg_cutoff)
            if len(fg_qualities) > 1:
                entry['configure_series_qualities'] = fg_qualities
            elif len(fg_qualities) == 1:
                entry['configure_series_quality'] = fg_qualities[0]
            else:
                entry['configure_series_quality'] = fg_qualities
            if path:
                entry['configure_series_path'] = path
            if entry.isvalid():
                entries.append(entry)
            else:
                log.error('Invalid entry created? %s' % entry)
                continue
            # Test mode logging
            if entry and task.options.test:
                log.verbose("Test mode. Entry includes:")
                for key, value in entry.items():
                    log.verbose('     {}: {}'.format(key.capitalize(), value))

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Sonarr, 'sonarr', api_ver=2)
