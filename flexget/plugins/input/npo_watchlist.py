from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

from jinja2 import TemplateSyntaxError

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.task import Task
from flexget.utils.search import normalize_unicode

from bs4 import BeautifulSoup
import unicodedata

import requests

import re
from datetime import datetime, timedelta

log = logging.getLogger('search_npo')
search_results_regex = re.compile('<a href="([^"]+)" data-scorecard="{&quot;name&quot;:&quot;zoeken')

class NPOWatchlist(object):
    """
        Produces entries for every episode on the user's npo.nl watchlist (Dutch public television).
        Entries can be downloaded using https://bitbucket.org/Carpetsmoker/download-npo
        
        If 'remove_accepted' is set to 'yes', the plugin will delete accepted entries from the watchlist after download is complete.
        
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
        'required': [],
        'additionalProperties': False
    }
    
    def _strip_accents(self, s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')

    
    def _get_profile(self, task, config):
        loginResponse = task.requests.get('https://mijn.npo.nl/inloggen')
        if loginResponse.url == 'http://www.npo.nl/profiel':
            log.debug('Already logged in')
            return loginResponse
        elif loginResponse.url <> 'https://mijn.npo.nl/inloggen':
            raise plugin.PluginError('Unexpected login page: {}'.format(loginResponse.url))
        
        loginPage = BeautifulSoup(loginResponse.content, 'html5lib')
        token = loginPage.find('input', attrs={'name': 'authenticity_token'})['value']
        
        email = config.get('email')
        password = config.get('password')
        
        profileResponse = task.requests.post('https://mijn.npo.nl/sessions', 
            {'authenticity_token': token, 
             'email': email,
             'password': password})

        if profileResponse.url == 'https://mijn.npo.nl/sessions':
            raise plugin.PluginError('Failed to login. Check username and password.')
        elif profileResponse.url <> 'http://www.npo.nl/profiel':
            raise plugin.PluginError('Unexpected profile page: {}'.format(profileResponse.url))
             
        return profileResponse

    def entry_complete(self, entry, task=None, **kwargs):
        log.info('Complete for {}'.format(entry))
        print task
        print kwargs
        
        
    def on_task_input(self, task, config):
        email = config.get('email')
        log.info('Retrieving npo.nl watchlist for {}'.format(email))

        profileResponse = self._get_profile(task, config)
        profilePage = BeautifulSoup(profileResponse.content, 'html5lib')
        
        entries = list()
        for listItem in profilePage.findAll('div', class_='list-item'):
            title = next(listItem.find('h4').stripped_strings)
            subtitle = listItem.find('h5').text 
            url = listItem.find('a')['href']
            removeUrl = listItem.find('a', class_='remove-button')['href']
            
            if subtitle == 'Serie':
                log.debug('Skipping series entry for {}'.format(title))
                continue

            e = Entry()
            e['title'] = '{} ({})'.format(title, subtitle)
            e['url'] = 'http://www.npo.nl' + url
            
            e['series_name'] = title
            e['series_name_plain'] = self._strip_accents(title)
            e['description'] = listItem.find('p').text
            e['remove_url'] = removeUrl
            
            if config.get('remove_accepted'):
                e.on_complete(self.entry_complete, task=task) 
            
            entries.append(e)
        
        return entries
    
    
    #def on_task_exit(self, task, config):
    #@plugin.priority(50)
    #def on_task_output(self, task, config):
    def entry_complete(self, e, task=None, **kwargs):
        if not e.accepted:
            log.warning('Not removing {} entry {}'.format(e.state, e['title']))
        elif 'remove_url' not in e:
            log.warning('No remove_url for {}, skipping'.format(e['title']))
        elif task.options.test:
            log.info('Would remove from watchlist: {}'.format(e['title']))
        else:
            log.info('Removing from watchlist: {}'.format(e['title']))
            
            try:
                deleteResponse = task.requests.delete(e['remove_url'])
            except requests.HTTPError:
                log.warning('Failed to remove {}, already removed (404)'.format(e['title']))
            else:
                if deleteResponse.status_code <> requests.codes.ok:
                    log.warning('Failed to remove {}, got status {}'.format(e['title'], deleteResponse.status_code))

            
@event('plugin.register')
def register_plugin():
    plugin.register(NPOWatchlist, 'npo_watchlist', api_ver=2)
