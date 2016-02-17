from __future__ import unicode_literals, division, absolute_import

import logging
from collections import MutableSet
from urlparse import urlparse

import requests
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('sonarr')


class SonarrSet(MutableSet):
    supported_ids = ['tvdb_id', 'tvrage_id', 'tvmaze_id', 'imdb_id', 'slug', 'sonarr_id']
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

    def series_request_builder(self, base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received series list request')
        url = '%s://%s:%s%s/api/series' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path)
        headers = {'X-Api-Key': api_key}
        return url, headers

    def profile_list_request(self, base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received profile list request')
        url = '%s://%s:%s%s/api/profile' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path)
        headers = {'X-Api-Key': api_key}
        return url, headers

    def series_add_request(self, base_url, port, api_key):
        pass

    def get_json(self, url, headers):
        try:
            return requests.get(url, headers=headers).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sonarr at %s. Error: %s' % (url, e))

    def post_json(self, request):
        try:
            return requests.post(request).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sonarr at %s. Error: %s' % (request['url'], e))


    def request_builder(self, base_url, request_type, port, api_key):
        if request_type == 'series':
            return self.series_request_builder(base_url, port, api_key)
        elif request_type == 'profile':
            return self.profile_list_request(base_url, port, api_key)
        else:
            raise plugin.PluginError('Received unknown API request, aborting.')

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

    def list_entries(self):
        series_url, series_headers = self.request_builder(self.config.get('base_url'), 'series', self.config.get('port'),
                                              self.config['api_key'])
        json = self.get_json(series_url, series_headers)

        # Retrieves Sonarr's profile list if include_data is set to true
        if self.config.get('include_data'):
            profile_url, profile_headers = self.request_builder(self.config.get('base_url'), 'profile', self.config.get('port'),
                                                   self.config['api_key'])
            profiles_json = self.get_json(profile_url, profile_headers)

        entries = []
        for show in json:
            fg_qualities = ''  # Initializes the quality parameter
            fg_cutoff = ''
            path = None
            if not show['monitored'] and self.config.get(
                    'only_monitored'):  # Checks if to retrieve just monitored shows
                continue
            if show['status'] == 'ended' and not self.config.get('include_ended'):  # Checks if to retrieve ended shows
                continue
            if self.config.get('include_data') and profiles_json:  # Check if to retrieve quality & path
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
                          imdb_id=show.get('imdbid'),
                          slug=show.get('titleSlug'),
                          sonarr_id=show.get('id'),
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
                log.debug('returning entry %s', entry)
                entries.append(entry)
            else:
                log.error('Invalid entry created? %s' % entry)
                continue

        return entries

    def add_show(self, entry):
        # TODO Sonarr makes it kinda hard to add shows to it, requiring details like array of seasons,
        # internal quality profile and path on disk. need to think if this is worth it.
        pass

    def remove_show(self, show):
        delete_series_url, delete_series_headers = self.request_builder(self.config.get('base_url'), 'series', self.config.get('port'),                                              self.config['api_key'])
        delete_series_url += '/%s' % show.get('id')
        response = requests.delete(delete_series_url, headers=delete_series_headers)

    @property
    def shows(self):
        if self._shows is None:
            self._shows = self.list_entries()
        return self._shows

    def _find_entry(self, entry):
        for sb_entry in self.shows:
            if any(entry.get(id) is not None and entry[id] == sb_entry[id] for id in self.supported_ids):
                return sb_entry
            if entry.get('title').lower() == sb_entry.get('title').lower():
                return sb_entry

    def __init__(self, config):
        self.config = config
        self._shows = None

    def __iter__(self):
        return (entry for entry in self.shows)

    def __len__(self):
        return len(self.shows)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def add(self, entry):
        if not self._find_entry(entry):
            show = self.add_show(entry)
            self._shows = None
            log.verbose('Successfully added movie %s to Sonarr', show['title'])
        else:
            log.debug('entry %s already exists in Sonarr list', entry)

    def discard(self, entry):
        show = self._find_entry(entry)
        if not show:
            log.debug('Did not find matching show in Sonarr for %s, skipping', entry)
            return
        self.remove_show(show)



class SonarrList(object):
    schema = SonarrSet.schema

    @staticmethod
    def get_list(config):
        return SonarrSet(config)

    def on_task_input(self, task, config):
        return list(SonarrSet(config))


class SonarrAdd(object):
    """Add all accepted elements in your couchpotato list."""
    schema = SonarrSet.schema

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        if task.manager.options.test:
            log.info('Not submitting to couchpotato because of test mode.')
            return
        thelist = SonarrSet(config)
        thelist |= task.accepted


class SonarrRemove(object):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    schema = SonarrSet.schema

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        if task.manager.options.test:
            log.info('Not submitting to couchpotato because of test mode.')
            return
        thelist = SonarrSet(config)
        thelist -= task.accepted


@event('plugin.register')
def register_plugin():
    plugin.register(SonarrList, 'sonarr_list', api_ver=2, groups=['list'])
    plugin.register(SonarrAdd, 'sonarr_add', api_ver=2)
    plugin.register(SonarrRemove, 'sonarr_remove', api_ver=2)
