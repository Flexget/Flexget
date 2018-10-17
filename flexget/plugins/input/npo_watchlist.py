# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from flexget.utils.soup import get_soup
from requests.exceptions import HTTPError, RequestException

from datetime import datetime, date, timedelta

import unicodedata
import re

log = logging.getLogger('search_npo')

requests = RequestSession(max_retries=3)
requests.add_domain_limiter(TimedLimiter('npostart.nl', '8 seconds'))


class NPOWatchlist(object):
    """
        Produces entries for every episode on the user's npostart.nl watchlist (Dutch public television).
        Entries can be downloaded using http://arp242.net/code/download-npo

        If 'remove_accepted' is set to 'yes', the plugin will delete accepted entries from the watchlist after download
            is complete.
        If 'max_episode_age_days' is set (and not 0), entries will only be generated for episodes broadcast in the last
            x days.  This only applies to episodes related to series the user is following.

        For example:
            npo_watchlist:
              email: aaaa@bbb.nl
              password: xxx
              remove_accepted: yes
              max_episode_age_days: 7
            accept_all: yes
            exec:
              fail_entries: yes
              auto_escape: yes
              on_output:
                for_accepted:
                  - download-npo -o "path/to/directory/{{series_name_plain}}" -f "{serie_titel} - {datum} \
                      {aflevering_titel} ({episode_id})" -t {{url}}
        """

    schema = {
        'type': 'object',
        'properties': {
            'email': {'type': 'string'},
            'password': {'type': 'string'},
            'remove_accepted': {'type': 'boolean', 'default': False},
            'max_episode_age_days': {'type': 'integer', 'default': -1},
        },
        'required': ['email', 'password'],
        'additionalProperties': False
    }

    csrf_token = None

    def _convert_plain(self, s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                       if not re.match('Mn|P[^cd]', unicodedata.category(c)))

    def _parse_date(self, date_text):
        return datetime.strptime(date_text, '%d-%m-%Y').date()

    def _get_page(self, task, config, url):
        self._login(task, config)
        try:
            log.debug('Fetching NPO profile page: %s', url)
            page_response = requests.get(url)
            if page_response.url != url:
                raise plugin.PluginError('Unexpected page: {} (expected {})'.format(page_response.url, url))
            return page_response
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % str(e))

    def _login(self, task, config):
        if 'isAuthenticatedUser' in requests.cookies:
            log.debug('Already logged in')
            return

        login_url = 'https://www.npostart.nl/login'
        login_api_url = 'https://www.npostart.nl/api/login'

        try:
            login_response = requests.get(login_url)
            if login_response.url != login_url:
                raise plugin.PluginError('Unexpected login page: {}'.format(login_response.url))

            login_page = get_soup(login_response.content)
            token = login_page.find('input', attrs={'name': '_token'})['value']

            email = config.get('email')
            password = config.get('password')

            profile_response = requests.post(login_api_url,
                                             {'_token': token,
                                              'username': email,
                                              'password': password})

            if 'isAuthenticatedUser' not in profile_response.cookies:
                raise plugin.PluginError('Failed to login. Check username and password.')
            log.debug('Succesfully logged in: %s', email)
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % str(e))

    def _get_favourites_entries(self, task, config, profileId):
        # Details of profile using the $profileId:
        # https://www.npostart.nl/api/account/@me/profile/$profileId  (?refresh=1)
        # XMLHttpRequest could also be done on, but is not reliable, because if a series is
        # bookmarked after episode is already broadcasted, it does not appear in this list.
        # https://www.npostart.nl/ums/accounts/@me/favourites/episodes?dateFrom=2018-06-04&dateTo=2018-06-05
        profile_details_url = 'https://www.npostart.nl/api/account/@me/profile/'

        entries = []
        try:
            profile = requests.get(profile_details_url + profileId).json()
            log.info('Retrieving favorites for profile %s', profile['name'])
            for favourite in profile['favourites']:
                if favourite['mediaType'] == 'series':
                    entries += self._get_series_episodes(task, config, favourite['mediaId'])
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % str(e))
        return entries

    def _get_series_episodes(self, task, config, mediaId, series_info=None, page=1):
        episode_tiles_url = 'https://www.npostart.nl/media/series/{0}/episodes'
        episode_tiles_parameters = {'page': str(page),
                                    'tileMapping': 'dedicated',
                                    'tileType': 'asset'}
        entries = []

        if not series_info:
            series_info = self._get_series_info(task, config, mediaId)
            if not series_info:  # if fetching series_info failed, return empty entries
                log.error('Failed to fetch series information for %s, skipping series', mediaId)
                return entries

        headers = {'Origin': 'https://www.npostart.nl',
                   'X-XSRF-TOKEN': requests.cookies['XSRF-TOKEN'],
                   'X-Requested-With': 'XMLHttpRequest'}
        if page > 1:
            headers['Referer'] = episode_tiles_url.format(mediaId) + '?page={0}'.format(page-1)  # referer from prev page

        log.debug('Retrieving episodes page %s for %s (%s)', page, series_info['npo_name'], mediaId)
        try:
            episodes = requests.get(episode_tiles_url.format(mediaId),
                                    params=episode_tiles_parameters,
                                    headers=headers).json()
            new_entries = self._parse_tiles(task, config, episodes['tiles'], series_info)
            entries += new_entries

            if new_entries and episodes['nextLink']:  # only fetch next page if we accepted any from current page
                log.debug('NextLink for more episodes: %s', episodes['nextLink'])
                entries += self._get_series_episodes(task, config, mediaId, series_info,
                                                     page=int(episodes['nextLink'].rsplit('page=')[1]))
        except RequestException as e:
            log.error('Request error: %s' % str(e))  # if it fails, just go to next favourite

        if not entries and page == 1:
            log.verbose('No new episodes found for %s (%s)', series_info['npo_name'], mediaId)
        return entries

    def _get_series_info(self, task, config, mediaId):
        series_info_url = 'https://www.npostart.nl/{0}'
        series_info = None
        log.verbose('Retrieving series info for %s', mediaId)
        try:
            response = requests.get(series_info_url.format(mediaId))
            log.debug('Series info found at: %s', response.url)
            page = get_soup(response.content)
            series = page.find('section', class_='npo-header-episode-meta')
            # create a stub to store the common values for all episodes of this series
            series_info = {'npo_url': response.url,  # we were redirected to the true URL
                           'npo_name': series.find('h1').text,
                           'npo_description': series.find('div', id='metaContent').find('p').text,
                           'npo_language': 'nl',  # hard-code the language as if in NL, for lookup plugins
                           'npo_version': page.find('meta', attrs={'name': 'generator'})['content']}  # include NPO website version
            log.debug('Parsed series info for: %s (%s)', series_info['npo_name'], mediaId)
        except RequestException as e:
            log.error('Request error: %s' % str(e))
        return series_info

    def _parse_tiles(self, task, config, tiles, series_info):
        max_age = config.get('max_episode_age_days')
        entries = []

        if tiles is not None:
            for tile in tiles:
                # there is only one list_item per tile
                for list_item in get_soup(tile).findAll('div', class_='npo-asset-tile-container'):
                    episode_id = list_item['id']
                    log.debug('Parsing episode: %s', episode_id)

                    url = list_item.find('a')['href']
                    # Check if the URL found to the episode matches the expected pattern
                    if len(url.split('/')) != 6:
                        log.verbose('Skipping %s, the URL has an unexpected pattern: %s', episode_id, url)
                        continue  # something is wrong; skip this episode

                    episode_name = list_item.find('h2')
                    if episode_name:
                        title = '{} ({})'.format(next(episode_name.stripped_strings), episode_id)
                    else:
                        title = '{}'.format(episode_id)
                    timer = next(list_item.find('div', class_='npo-asset-tile-timer').stripped_strings)
                    remove_url = list_item.find('div', class_='npo-asset-tile-delete')

                    not_available = list_item.find('div', class_='npo-asset-tile-availability')['data-to']
                    if not_available:
                        log.debug('Skipping %s, no longer available', title)
                        continue

                    entry_date = url.split('/')[-2]
                    entry_date = self._parse_date(entry_date)

                    if max_age >= 0 and date.today() - entry_date > timedelta(days=max_age):
                        log.debug('Skipping %s, aired on %s', title, entry_date)
                        continue

                    e = Entry(series_info)
                    e['url'] = url
                    e['title'] = title
                    e['series_name'] = series_info['npo_name']
                    e['series_name_plain'] = self._convert_plain(series_info['npo_name'])
                    e['series_date'] = entry_date
                    e['series_id_type'] = 'date'
                    e['npo_id'] = episode_id
                    e['npo_runtime'] = timer.strip('min').strip()
                    e['language'] = series_info['npo_language']

                    if remove_url and remove_url['data-link']:
                        e['remove_url'] = remove_url['data-link']
                        if config.get('remove_accepted'):
                            e.on_complete(self.entry_complete, task=task)
                    entries.append(e)

        return entries

    def on_task_input(self, task, config):
        # On https://www.npostart.nl/account-profile get the value for the profileId that is in use
        # Details of this account you can get at: https://www.npostart.nl/api/account/@me
        account_profile_url = 'https://www.npostart.nl/account-profile'

        email = config.get('email')
        log.verbose('Retrieving NPOStart profiles for account %s', email)

        profilejson = self._get_page(task, config, account_profile_url).json()
        if 'profileId' not in profilejson:
            raise plugin.PluginError('Failed to fetch profile for NPO account')
        profileId = profilejson['profileId']
        entries = self._get_favourites_entries(task, config, profileId)
        return entries

    def entry_complete(self, e, task=None):
        if not e.accepted:
            log.warning('Not removing %s entry %s', e.state, e['title'])
        elif 'remove_url' not in e:
            log.warning('No remove_url for %s, skipping', e['title'])
        elif task.options.test:
            log.info('Would remove from watchlist: %s', e['title'])
        else:
            log.info('Removing from watchlist: %s', e['title'])

            headers = {
                'Origin': 'https://www.npostart.nl',
                'Referer': 'https://www.npostart.nl/mijn_npo',
                'X-XSRF-TOKEN': requests.cookies['XSRF-TOKEN'],
                'X-Requested-With': 'XMLHttpRequest'
            }

            try:
                delete_response = requests.post(e['remove_url'], headers=headers, cookies=requests.cookies)
            except HTTPError as error:
                log.error('Failed to remove %s, got status %s', e['title'], error.response.status_code)
            else:
                if delete_response.status_code != requests.codes.ok:
                    log.warning('Failed to remove %s, got status %s', e['title'], delete_response.status_code)


@event('plugin.register')
def register_plugin():
    plugin.register(NPOWatchlist, 'npo_watchlist', api_ver=2, interfaces=['task'])
