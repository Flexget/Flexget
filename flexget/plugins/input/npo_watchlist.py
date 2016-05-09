from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

from bs4 import BeautifulSoup

import unicodedata
import requests
import re

log = logging.getLogger('search_npo')
search_results_regex = re.compile('<a href="([^"]+)" data-scorecard="{&quot;name&quot;:&quot;zoeken')


class NPOWatchlist(object):
    """
        Produces entries for every episode on the user's npo.nl watchlist (Dutch public television).
        Entries can be downloaded using https://bitbucket.org/Carpetsmoker/download-npo
        
        If 'remove_accepted' is set to 'yes', the plugin will delete accepted entries from the watchlist after download
        is complete.
        
        For example:
            npo_watchlist:
              email: aaaa@bbb.nl
              password: xxx
              remove_accepted: yes
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
            'remove_accepted': {'type': 'boolean', 'default': False}
        },
        'required': ['email', 'password'],
        'additionalProperties': False
    }
    
    csrf_token = None
    
    def _strip_accents(self, s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')

    def _get_profile(self, task, config):
        login_response = task.requests.get('https://mijn.npo.nl/inloggen')
        if login_response.url == 'http://www.npo.nl/profiel':
            log.debug('Already logged in')
            return login_response
        elif login_response.url != 'https://mijn.npo.nl/inloggen':
            raise plugin.PluginError('Unexpected login page: {}'.format(login_response.url))
        
        login_page = BeautifulSoup(login_response.content, 'html5lib')
        token = login_page.find('input', attrs={'name': 'authenticity_token'})['value']
        
        email = config.get('email')
        password = config.get('password')
        
        profile_response = task.requests.post('https://mijn.npo.nl/sessions', 
            {'authenticity_token': token, 
             'email': email,
             'password': password})

        if profile_response.url == 'https://mijn.npo.nl/sessions':
            raise plugin.PluginError('Failed to login. Check username and password.')
        elif profile_response.url != 'https://mijn.npo.nl/profiel':
            raise plugin.PluginError('Unexpected profile page: {}'.format(profile_response.url))
        
        return profile_response

    def on_task_input(self, task, config):
        email = config.get('email')
        log.info('Retrieving npo.nl watchlist for %s', email)

        profile_response = self._get_profile(task, config)
        profile_page = BeautifulSoup(profile_response.content, 'html5lib')
        
        self.csrf_token = profile_page.find('meta', attrs={'name': 'csrf-token'})['content']
        
        entries = list()
        for listItem in profile_page.findAll('div', class_='list-item'):
            title = next(listItem.find('h4').stripped_strings)
            subtitle = listItem.find('h5').text 
            url = listItem.find('a')['href']
            remove_url = listItem.find('a', class_='remove-button')['href']
            
            if subtitle == 'Serie':
                log.debug('Skipping series entry for %s', title)
                continue

            e = Entry()
            e['title'] = '{} ({})'.format(title, subtitle)
            e['url'] = url
            
            e['series_name'] = title
            e['series_name_plain'] = self._strip_accents(title)
            e['description'] = listItem.find('p').text
            e['remove_url'] = remove_url
            
            if config.get('remove_accepted'):
                e.on_complete(self.entry_complete, task=task) 
            
            entries.append(e)
        
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
                'Referer': 'https://mijn.npo.nl/profiel',
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
