from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup

from datetime import date, timedelta

import unicodedata
import requests
import re

log = logging.getLogger('search_npo')
fragment_regex = re.compile('[A-Z][^/]+/')
date_regex = re.compile('([1-3]?[0-9]) ([a-z]{3}) ([0-9]{4})')
days_ago_regex = re.compile('([0-9]+) dagen geleden')
months = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']


class NPOWatchlist(object):
    """
        Produces entries for every episode on the user's npo.nl watchlist (Dutch public television).
        Entries can be downloaded using http://arp242.net/code/download-npo

        If 'remove_accepted' is set to 'yes', the plugin will delete accepted entries from the watchlist after download
            is complete.
        If 'max_episode_age_days' is set (and not 0), entries will only be generated for episodes broadcast in the last x days.
            This only applies to episodes related to series the user is following.

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
                  - download-npo -o "path/to/directory/{{series_name_plain}}" -f "{serie_titel} - {datum} {aflevering_titel} ({episode_id})" -t {{url}}
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

    def _strip_accents(self, s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                       if unicodedata.category(c) != 'Mn')

    def _prefix_url(self, prefix, url):
        if ':' not in url:
            url = prefix + url
        
        return url
        
    def _parse_date(self, date_text):
        date_match = date_regex.search(date_text)
        days_ago_match = days_ago_regex.search(date_text)
        first_word = date_text.split(' ')[0].lower().strip()
        
        if date_match:
            day = int(date_match.group(1))
            month = months.index(date_match.group(2))+1
            year = int(date_match.group(3))
            return date(year, month, day)
        elif days_ago_match:
            days_ago = int(days_ago_match.group(1))
            return date.today() - timedelta(days=days_ago)
        elif first_word in ['vandaag', 'vanochtend', 'vanmiddag', 'vanavond']:
            return date.today()
        elif first_word == 'gisteren':
            return date.today() - timedelta(days=1)
        elif first_word == 'eergisteren':
            return date.today() - timedelta(days=2)
        elif first_word == 'kijk':
            return None
        else:
            log.error("Cannot understand date '%s'", date_text)
            return date.today()
        
    def _get_page(self, task, config, url):
        login_response = task.requests.get(url)
        if login_response.url == url:
            log.debug('Already logged in')
            return login_response
        elif login_response.url != 'https://mijn.npo.nl/inloggen':
            raise plugin.PluginError('Unexpected login page: {}'.format(login_response.url))

        login_page = get_soup(login_response.content)
        token = login_page.find('input', attrs={'name': 'authenticity_token'})['value']

        email = config.get('email')
        password = config.get('password')

        profile_response = task.requests.post('https://mijn.npo.nl/sessions',
                                              {'authenticity_token': token,
                                               'email': email,
                                               'password': password})

        if profile_response.url == 'https://mijn.npo.nl/sessions':
            raise plugin.PluginError('Failed to login. Check username and password.')
        elif profile_response.url != url:
            raise plugin.PluginError('Unexpected page: {} (expected {})'.format(profile_response.url, url))

        return profile_response

    def _get_watchlist_entries(self, task, config):
        email = config.get('email')
        log.info('Retrieving npo.nl episode watchlist for %s', email)

        response = self._get_page(task, config, 'https://mijn.npo.nl/profiel/kijklijst')
        page = get_soup(response.content)

        self.csrf_token = page.find('meta', attrs={'name': 'csrf-token'})['content']

        entries = list()
        for listItem in page.findAll('div', class_='watch-list-item'):
            url = listItem.find('a')['href']
            series_name = next(listItem.find('h3').stripped_strings)
            remove_url = listItem.find('a', class_='unwatch-confirm')['href']
            entry_date = self._parse_date(listItem.find('span', class_='global__content-info').text)
            
            episode_id = url.split('/')[-1]
            title = '{} ({})'.format(series_name, episode_id)

            e = Entry()
            e['url'] = self._prefix_url('https://mijn.npo.nl', url)
            e['title'] = title
            e['series_name'] = series_name
            e['series_name_plain'] = self._strip_accents(series_name)
            e['series_date'] = entry_date
            e['description'] = listItem.find('p').text
            e['remove_url'] = self._prefix_url('https://mijn.npo.nl', remove_url)

            if config.get('remove_accepted'):
                e.on_complete(self.entry_complete, task=task)

            entries.append(e)

        return entries
        
    def _get_series_episodes(self, task, config, series_name, series_url):
        log.info('Retrieving new episodes for %s', series_name)
        response = task.requests.get(series_url + '/search?category=broadcasts')
        page = get_soup(response.content)

        if page.find('div', class_='npo3-show-items'):
            log.debug('Parsing as npo3')
            entries = self._parse_episodes_npo3(task, config, series_name, page)
        else:
            log.debug('Parsing as std')
            entries = self._parse_episodes_std(task, config, series_name, page)
            
        if not entries:
            log.warning('No episodes found for %s', series_name)

        return entries

    def _parse_episodes_npo3(self, task, config, series_name, page):
        max_age = config.get('max_episode_age_days')
        
        entries = list()
        for listItem in page.findAll('div', class_='item'):
            url = listItem.find('a')['href']
            title = listItem.find('h3').text
            
            episode_id = url.split('/')[-1]
            title = '{} ({})'.format(title, episode_id)
            
            entry_date = list(listItem.find('h4').stripped_strings)[1]
            entry_date = self._parse_date(entry_date)
            if max_age >= 0 and (date.today() - entry_date) > timedelta(days=max_age):
                log.debug('Skipping %s, aired on %s', title, entry_date)
                continue
                
            e = Entry()
            e['url'] = self._prefix_url('http://www.npo.nl', url)
            e['title'] = title
            e['series_name'] = series_name
            e['series_name_plain'] = self._strip_accents(series_name)
            e['series_date'] = entry_date
            e['description'] = listItem.find('p').text

            entries.append(e)
        
        return entries
        
    def _parse_episodes_std(self, task, config, series_name, page):
        max_age = config.get('max_episode_age_days')

        entries = list()
        for listItem in page.findAll('div', class_='list-item'):
            url = listItem.find('a')['href']
            title = next(listItem.find('h4').stripped_strings)
            subtitle = listItem.find('h5').text
            
            episode_id = url.split('/')[-1]
            title = '{} ({})'.format(title, episode_id)
            
            if listItem.find('div', class_='program-not-available'):
                log.debug('Skipping %s, no longer available', title)
                continue
            elif fragment_regex.search(url):
                log.debug('Skipping fragment: %s', title)
                continue
            
            entry_date = self._parse_date(subtitle)
            if max_age >= 0 and (date.today() - entry_date) > timedelta(days=max_age):
                log.debug('Skipping %s, aired on %s', title, entry_date)
                continue
                
            e = Entry()
            e['url'] = self._prefix_url('http://www.npo.nl', url)
            e['title'] = title
            e['series_name'] = series_name
            e['series_name_plain'] = self._strip_accents(series_name)
            e['series_date'] = entry_date
            e['description'] = listItem.find('p').text

            entries.append(e)
        
        return entries
            
    def _get_favorites_entries(self, task, config):
        email = config.get('email')
        max_age = config.get('max_episode_age_days')

        log.info('Retrieving npo.nl favorite series for %s', email)
        response = self._get_page(task, config, 'https://mijn.npo.nl/profiel/favorieten')
        page = get_soup(response.content)

        entries = list()
        for listItem in page.findAll('div', class_='thumb-item'):
            url = listItem.find('a')['href']
            
            if url == '/profiel/favorieten/favorieten-toevoegen':
                log.debug("Skipping 'add favorite' button")
                continue

            url = self._prefix_url('https://mijn.npo.nl', url)
            series_name = next(listItem.find('div', class_='thumb-item__title').stripped_strings)
            
            last_aired_text = listItem.find('div', class_='thumb-item__subtitle').text
            last_aired_text = last_aired_text.rsplit('Laatste aflevering ')[-1]
            last_aired = self._parse_date(last_aired_text)
            
            if last_aired is None:
                log.info('Series %s did not yet start', series_name)
                continue
            elif max_age >= 0 and (date.today() - last_aired) > timedelta(days=max_age):
                log.debug('Skipping %s, last aired on %s', series_name, last_aired)
                continue
            elif (date.today() - last_aired) > timedelta(days=365*2):
                log.info('Series %s last aired on %s', series_name, last_aired)
            
            entries += self._get_series_episodes(task, config, series_name, url)

        return entries
        
    def on_task_input(self, task, config):
        entries = self._get_watchlist_entries(task, config)
        entries += self._get_favorites_entries(task, config)
        
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
                'Origin': 'https://mijn.npo.nl/',
                'Referer': 'https://mijn.npo.nl/profiel/kijklijst',
                'X-CSRF-Token': self.csrf_token,
                'X-Requested-With': 'XMLHttpRequest'
            }

            try:
                delete_response = task.requests.delete(e['remove_url'], headers=headers)
            except requests.HTTPError as error:
                log.error('Failed to remove %s, got status %s', e['title'], error.response.status_code)
            else:
                if delete_response.status_code != requests.codes.ok:
                    log.warning('Failed to remove %s, got status %s', e['title'], delete_response.status_code)


@event('plugin.register')
def register_plugin():
    plugin.register(NPOWatchlist, 'npo_watchlist', api_ver=2, groups=['list'])
