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
requests.add_domain_limiter(TimedLimiter('npo.nl', '5 seconds'))


class NPOWatchlist(object):
    """
        Produces entries for every episode on the user's npo.nl watchlist (Dutch public television).
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

    def _login(self, task, config):
        if 'isAuthenticatedUser' in requests.cookies:
            log.debug('Already logged in')
            return

        login_url = 'https://www.npo.nl/login'
        login_api_url = 'https://www.npo.nl/api/login'

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
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % e.args[0])

    def _get_page(self, task, config, url):
        self._login(task, config)

        try:
            page_response = requests.get(url)
            if page_response.url != url:
                raise plugin.PluginError('Unexpected page: {} (expected {})'.format(page_response.url, url))

            return page_response
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % e.args[0])

    def _get_watchlist_entries(self, task, config, page):
        watchlist = page.find('div', attrs={'id': 'component-grid-watchlist'})
        return self._parse_tiles(task, config, watchlist)

    _series_info = dict()

    def _get_series_info(self, task, config, episode_name, episode_url):
        log.info('Retrieving series info for %s', episode_name)
        try:
            response = requests.get(episode_url)
            page = get_soup(response.content)

            series_url = page.find('a', class_='npo-episode-header-program-info')['href']

            if series_url not in self._series_info:
                response = requests.get(series_url)
                page = get_soup(response.content)

                series_info = self._parse_series_info(task, config, page, series_url)
                self._series_info[series_url] = series_info

            return self._series_info[series_url]
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % e.args[0])

    def _parse_series_info(self, task, config, page, series_url):
        tvseries = page.find('section', class_='npo-header-episode-meta')
        series_info = Entry()  # create a stub to store the common values for all episodes of this series
        series_info['npo_url'] = series_url
        series_info['npo_name'] = tvseries.find('h1').text
        series_info['npo_description'] = tvseries.find('div', id='metaContent').find('p').text
        series_info['npo_language'] = 'nl'  # hard-code the language as if in NL, for loookup plugins
        return series_info

    def _get_series_episodes(self, task, config, series_name, series_url):
        log.info('Retrieving new episodes for %s', series_name)
        try:
            response = requests.get(series_url)
            page = get_soup(response.content)

            series_info = self._parse_series_info(task, config, page, series_url)
            episodes = page.find('div', id='component-grid-episodes')
            entries = self._parse_tiles(task, config, episodes, series_info)

            if not entries:
                log.warning('No episodes found for %s', series_name)

            return entries
        except RequestException as e:
            raise plugin.PluginError('Request error: %s' % e.args[0])

    def _parse_tiles(self, task, config, tiles, series_info=None):
        max_age = config.get('max_episode_age_days')
        entries = list()

        if tiles is not None:
            for list_item in tiles.findAll('div', class_='npo-asset-tile-container'):
                url = list_item.find('a')['href']
                episode_name = next(list_item.find('h2').stripped_strings)
                timer = next(list_item.find('div', class_='npo-asset-tile-timer').stripped_strings)
                remove_url = list_item.find('div', class_='npo-asset-tile-delete')

                episode_id = url.split('/')[-1]
                title = '{} ({})'.format(episode_name, episode_id)

                not_available = list_item.find('div', class_='npo-asset-tile-availability')['data-to']
                if not_available:
                    log.debug('Skipping %s, no longer available', title)
                    continue

                entry_date = url.split('/')[4]
                entry_date = self._parse_date(entry_date)

                if max_age >= 0 and (date.today() - entry_date) > timedelta(days=max_age):
                    log.debug('Skipping %s, aired on %s', title, entry_date)
                    continue

                if not series_info:
                    tile_series_info = self._get_series_info(task, config, episode_name, url)
                else:
                    tile_series_info = series_info

                series_name = tile_series_info['npo_name']

                e = Entry()
                e['url'] = url
                e['title'] = title
                e['series_name'] = series_name
                e['series_name_plain'] = self._convert_plain(series_name)
                e['series_date'] = entry_date
                e['series_id_type'] = 'date'
                e['npo_url'] = tile_series_info['npo_url']
                e['npo_name'] = tile_series_info['npo_name']
                e['npo_description'] = tile_series_info['npo_description']
                e['npo_language'] = tile_series_info['npo_language']
                e['npo_runtime'] = timer.strip('min').strip()
                e['language'] = tile_series_info['npo_language']

                if remove_url and remove_url['data-link']:
                    e['remove_url'] = remove_url['data-link']

                    if config.get('remove_accepted'):
                        e.on_complete(self.entry_complete, task=task)

                entries.append(e)

        return entries

    def _get_favorites_entries(self, task, config, page):
        max_age = config.get('max_episode_age_days')
        if max_age >= 3:
            log.warning('If max_episode_age_days is 3 days or more, the plugin will still check all series')
        elif max_age > -1:
            return self._get_recent_entries(task, config, page)

        series = page.find('div', attrs={'id': 'component-grid-favourite-series'})

        entries = list()
        for list_item in series.findAll('div', class_='npo-ankeiler-tile-container'):
            url = list_item.find('a')['href']
            series_name = next(list_item.find('h2').stripped_strings)

            entries += self._get_series_episodes(task, config, series_name, url)

        return entries

    def _get_recent_entries(self, task, config, page):
        max_age = config.get('max_episode_age_days')

        episodes = page.find('div', id='grid-favourite-episodes-today')
        entries = self._parse_tiles(task, config, episodes)

        if max_age >= 1:
            episodes = page.find('div', id='grid-favourite-episodes-yesterday')
            entries += self._parse_tiles(task, config, episodes)

        if max_age >= 2:
            episodes = page.find('div', id='grid-favourite-episodes-day-before-yesterday')
            entries += self._parse_tiles(task, config, episodes)

        return entries

    def on_task_input(self, task, config):
        email = config.get('email')
        log.info('Retrieving npo.nl watchlist for %s', email)

        response = self._get_page(task, config, 'https://www.npo.nl/mijn_npo')
        page = get_soup(response.content)

        entries = self._get_watchlist_entries(task, config, page)
        entries += self._get_favorites_entries(task, config, page)

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
                'Origin': 'https://www.npo.nl',
                'Referer': 'https://www.npo.nl/mijn_npo',
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
