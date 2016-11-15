from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse

import json
import logging
from collections import MutableSet

import requests
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('sonarr_list')


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

    def lookup_request(self, base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received series lookup request')
        url = '%s://%s:%s%s/api/series/lookup?term=' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path)
        headers = {'X-Api-Key': api_key}
        return url, headers

    def profile_list_request(self, base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received profile list request')
        url = '%s://%s:%s%s/api/profile' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path)
        headers = {'X-Api-Key': api_key}
        return url, headers

    def rootfolder_request(self, base_url, port, api_key):
        parsedurl = urlparse(base_url)
        log.debug('Received rootfolder list request')
        url = '%s://%s:%s%s/api/Rootfolder' % (parsedurl.scheme, parsedurl.netloc, port, parsedurl.path)
        headers = {'X-Api-Key': api_key}
        return url, headers

    def get_json(self, url, headers):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                raise plugin.PluginError('Invalid response received from Sonarr: %s' % response.content)
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sonarr at %s. Error: %s' % (url, e))

    def post_json(self, url, headers, data):
        try:
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 201:
                return response.json()
            else:
                raise plugin.PluginError('Invalid response received from Sonarr: %s' % response.content)
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sonarr at %s. Error: %s' % (url, e))

    def request_builder(self, base_url, request_type, port, api_key):
        if request_type == 'series':
            return self.series_request_builder(base_url, port, api_key)
        elif request_type == 'profile':
            return self.profile_list_request(base_url, port, api_key)
        elif request_type == 'lookup':
            return self.lookup_request(base_url, port, api_key)
        elif request_type == 'rootfolder':
            return self.rootfolder_request(base_url, port, api_key)
        else:
            raise plugin.PluginError('Received unknown API request, aborting.')

    def translate_quality(self, quality_name):
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

        allowed_qualities = [self.translate_quality(quality['quality']['name']) for quality in quality_profile['items']
                             if quality['allowed']]
        cutoff = self.translate_quality(quality_profile['cutoff']['name'])

        return allowed_qualities, cutoff

    def list_entries(self):
        series_url, series_headers = self.request_builder(self.config.get('base_url'), 'series',
                                                          self.config.get('port'), self.config['api_key'])
        json = self.get_json(series_url, series_headers)

        # Retrieves Sonarr's profile list if include_data is set to true
        if self.config.get('include_data'):
            profile_url, profile_headers = self.request_builder(self.config.get('base_url'), 'profile',
                                                                self.config.get('port'),
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
        log.debug('searching for show match for %s using Sonarr', entry)
        lookup_series_url, lookup_series_headers = self.request_builder(self.config.get('base_url'), 'lookup',
                                                                        self.config.get('port'), self.config['api_key'])
        if entry.get('tvdb_id'):
            lookup_series_url += 'tvdb:%s' % entry.get('tvdb_id')
        else:
            lookup_series_url += entry.get('title')
        lookup_results = self.get_json(lookup_series_url, headers=lookup_series_headers)
        if not lookup_results:
            log.debug('could not find series match to %s', entry)
            return
        else:
            if len(lookup_results) > 1:
                log.debug('got multiple results for Sonarr, using first one')
        show = lookup_results[0]
        log.debug('using show %s', show)
        # Getting rootfolder
        rootfolder_series_url, rootfolder_series_headers = self.request_builder(self.config.get('base_url'),
                                                                                'rootfolder', self.config.get('port'),
                                                                                self.config['api_key'])
        rootfolder = self.get_json(rootfolder_series_url, headers=rootfolder_series_headers)

        # Setting defaults for Sonarr
        show['profileId'] = 1
        show['qualityProfileId '] = 1
        show['rootFolderPath'] = rootfolder[0]['path']

        series_url, series_headers = self.request_builder(self.config.get('base_url'), 'series',
                                                          self.config.get('port'), self.config['api_key'])
        log.debug('adding show %s to sonarr', show)
        returned_show = self.post_json(series_url, headers=series_headers, data=json.dumps(show))
        return returned_show

    def remove_show(self, show):
        delete_series_url, delete_series_headers = self.request_builder(self.config.get('base_url'), 'series',
                                                                        self.config.get('port'), self.config['api_key'])
        delete_series_url += '/%s' % show.get('sonarr_id')
        requests.delete(delete_series_url, headers=delete_series_headers)

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

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

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
            log.verbose('Successfully added show %s to Sonarr', show['title'])
        else:
            log.debug('entry %s already exists in Sonarr list', entry)

    def discard(self, entry):
        show = self._find_entry(entry)
        if not show:
            log.debug('Did not find matching show in Sonarr for %s, skipping', entry)
            return
        self.remove_show(show)
        log.verbose('removed show %s from Sonarr', show['title'])

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

    def get(self, entry):
        return self._find_entry(entry)


class SonarrList(object):
    schema = SonarrSet.schema

    @staticmethod
    def get_list(config):
        return SonarrSet(config)

    def on_task_input(self, task, config):
        return list(SonarrSet(config))


@event('plugin.register')
def register_plugin():
    plugin.register(SonarrList, 'sonarr_list', api_ver=2, groups=['list'])
