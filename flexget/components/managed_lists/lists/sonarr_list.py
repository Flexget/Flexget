from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from collections import MutableSet

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests

log = logging.getLogger('sonarr_list')

SERIES_ENDPOINT = 'series'
LOOKUP_ENDPOINT = 'series/lookup'
PROFILE_ENDPOINT = 'profile'
ROOTFOLDER_ENDPOINT = 'Rootfolder'
DELETE_ENDPOINT = 'series/{}'

# Sonarr qualities that do no exist in Flexget
QUALITY_MAP = {'Raw-HD': 'remux', 'DVD': 'dvdrip'}


class SonarrSet(MutableSet):
    supported_ids = ['tvdb_id', 'tvrage_id', 'tvmaze_id', 'imdb_id', 'slug', 'sonarr_id']
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string', 'default': 'http://localhost'},
            'base_path': {'type': 'string', 'default': ''},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_ended': {'type': 'boolean', 'default': True},
            'only_monitored': {'type': 'boolean', 'default': True},
            'include_data': {'type': 'boolean', 'default': False},
            'search_missing_episodes': {'type': 'boolean', 'default': True},
            'ignore_episodes_without_files': {'type': 'boolean', 'default': False},
            'ignore_episodes_with_files': {'type': 'boolean', 'default': False},
            'profile_id': {'type': 'integer', 'default': 1},
            'season_folder': {'type': 'boolean', 'default': False},
            'monitored': {'type': 'boolean', 'default': True},
            'root_folder_path': {'type': 'string'},
            'series_type': {
                'type': 'string',
                'enum': ['standard', 'daily', 'anime'],
                'default': 'standard',
            },
            'tags': {'type': 'array', 'items': {'type': 'integer'}, 'default': [0]},
        },
        'required': ['api_key'],
        'additionalProperties': False,
    }

    def _sonarr_request(self, endpoint, term=None, method='get', data=None):
        base_url = self.config['base_url']
        port = self.config['port']
        base_path = self.config['base_path']
        url = '{}:{}{}/api/{}'.format(base_url, port, base_path, endpoint)
        headers = {'X-Api-Key': self.config['api_key']}
        if term:
            url += '?term={}'.format(term)
        try:
            rsp = requests.request(method, url, headers=headers, json=data)
            data = rsp.json()
            log.trace('sonarr response: %s', data)
            return data
        except RequestException as e:
            base_msg = 'Sonarr returned an error. {}'
            if e.response is not None:
                error = e.response.json()[0]
                error = '{}: {} \'{}\''.format(
                    error['errorMessage'], error['propertyName'], error['attemptedValue']
                )
            else:
                error = str(e)
            raise plugin.PluginError(base_msg.format(error))

    def translate_quality(self, quality_name):
        """
        Translate Sonarr's qualities to ones recognize by Flexget
        """
        if quality_name in QUALITY_MAP:
            return QUALITY_MAP[quality_name]
        return quality_name.replace('-', ' ').lower()

    def quality_requirement_builder(self, quality_profile):
        allowed_qualities = [
            self.translate_quality(quality['quality']['name'])
            for quality in quality_profile['items']
            if quality['allowed']
        ]
        cutoff = self.translate_quality(quality_profile['cutoff']['name'])

        return allowed_qualities, cutoff

    def list_entries(self, filters=True):
        shows = self._sonarr_request(SERIES_ENDPOINT)
        profiles_dict = {}
        # Retrieves Sonarr's profile list if include_data is set to true
        include_data = self.config.get('include_data')
        if include_data:
            profiles = self._sonarr_request(PROFILE_ENDPOINT)
            profiles_dict = {profile['id']: profile for profile in profiles}

        entries = []
        for show in shows:
            fg_qualities = []  # Initializes the quality parameter
            fg_cutoff = None
            path = show.get('path') if include_data else None
            if filters:
                # Checks if to retrieve just monitored shows
                if not show['monitored'] and self.config.get('only_monitored'):
                    continue
                # Checks if to retrieve ended shows
                if show['status'] == 'ended' and not self.config.get('include_ended'):
                    continue
            profile = profiles_dict.get(show['profileId'])
            if profile:
                fg_qualities, fg_cutoff = self.quality_requirement_builder(profile)

            entry = Entry(
                title=show['title'],
                url='',
                series_name=show['title'],
                tvdb_id=show.get('tvdbId'),
                tvrage_id=show.get('tvRageId'),
                tvmaze_id=show.get('tvMazeId'),
                imdb_id=show.get('imdbid'),
                slug=show.get('titleSlug'),
                sonarr_id=show.get('id'),
            )
            if len(fg_qualities) > 1:
                entry['configure_series_qualities'] = fg_qualities
            elif len(fg_qualities) == 1:
                entry['configure_series_quality'] = fg_qualities[0]
            if path:
                entry['configure_series_path'] = path
            if fg_cutoff:
                entry['configure_series_target'] = fg_cutoff

            if entry.isvalid():
                log.debug('returning entry %s', entry)
                entries.append(entry)
            else:
                log.error('Invalid entry created? %s' % entry)
                continue

        return entries

    def add_show(self, entry):
        log.debug('searching for show match for %s using Sonarr', entry)
        term = 'tvdb:{}'.format(entry['tvdb_id']) if entry.get('tvdb_id') else entry['title']
        lookup_results = self._sonarr_request(LOOKUP_ENDPOINT, term=term)
        if not lookup_results:
            log.debug('could not find series match to %s', entry)
            return
        elif len(lookup_results) > 1:
            log.debug('got multiple results for Sonarr, using first one')
        show = lookup_results[0]
        log.debug('using show %s', show)

        # Getting root folder
        if self.config.get('root_folder_path'):
            root_path = self.config['root_folder_path']
        else:
            root_folder = self._sonarr_request(ROOTFOLDER_ENDPOINT)
            root_path = root_folder[0]['path']

        # Setting defaults for Sonarr
        show['profileId'] = self.config.get('profile_id')
        show['qualityProfileId'] = self.config.get('profile_id')
        show['seasonFolder'] = self.config.get('season_folder')
        show['monitored'] = self.config.get('monitored')
        show['seriesType'] = self.config.get('series_type')
        show['tags'] = self.config.get('tags')
        show['rootFolderPath'] = root_path
        show['addOptions'] = {
            "ignoreEpisodesWithFiles": self.config.get('ignore_episodes_with_files'),
            "ignoreEpisodesWithoutFiles": self.config.get('ignore_episodes_without_files'),
            "searchForMissingEpisodes": self.config.get('search_missing_episodes'),
        }

        log.debug('adding show %s to sonarr', show)
        returned_show = self._sonarr_request(SERIES_ENDPOINT, method='post', data=show)
        return returned_show

    def remove_show(self, show):
        log.debug('sending sonarr delete show request')
        self._sonarr_request(DELETE_ENDPOINT.format(show['sonarr_id']), method='delete')

    def shows(self, filters=True):
        if self._shows is None:
            self._shows = self.list_entries(filters=filters)
        return self._shows

    def _find_entry(self, entry, filters=True):
        for show in self.shows(filters=filters):
            if any(
                entry.get(id) is not None and entry[id] == show[id] for id in self.supported_ids
            ):
                return show
            if entry.get('title').lower() == show.get('title').lower():
                return show

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    def __init__(self, config):
        self.config = config
        self._shows = None

    def __iter__(self):
        return (entry for entry in self.shows())

    def __len__(self):
        return len(self.shows())

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    def add(self, entry):
        if not self._find_entry(entry, filters=False):
            show = self.add_show(entry)
            if show:
                self._shows = None
                log.verbose('Successfully added show %s to Sonarr', show['title'])
        else:
            log.debug('entry %s already exists in Sonarr list', entry)

    def discard(self, entry):
        show = self._find_entry(entry, filters=False)
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
    plugin.register(SonarrList, 'sonarr_list', api_ver=2, interfaces=['task', 'list'])
