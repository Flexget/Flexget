from __future__ import unicode_literals, division, absolute_import
import logging
import re

import feedparser

from flexget import plugin
from flexget.event import event
from flexget.utils.imdb import extract_id
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('imdb_list')

USER_ID_RE = r'^ur\d{7,8}$'


class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'string',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form urXXXXXXX'
            },
            'list': {'type': 'string'}
        },
        'required': ['list', 'user_id'],
        'additionalProperties': False
    }

    @cached('imdb_list', persist='2 hours')
    def on_task_input(self, task, config):
        log.verbose('Retrieving list %s ...' % config['list'])

        # Get the imdb list in HTML format
        if config['list'] in ['watchlist', 'ratings', 'checkins']:
            url = 'http://imdb.com/user/%s/%s' % (config['user_id'], config['list'])
        else:
            url = 'http://imdb.com/list/%s' % config['list']

        log.debug('Requesting %s' % url)
        page = task.requests.get(url)
        log.debug('Response: %s (%s)' % (page.status_code, page.reason))

        if page.status_code != 200:
            raise plugin.PluginError('Unable to get imdb list. Either list is private or does not exist.')

        soup = get_soup(page.text)
        divs = soup.find_all('div', attrs={'class':'title'})
        soup = get_soup(str(divs))
        links = soup.find_all('a')

        # Create an Entry for each movie in the list
        entries = []
        for a in links:
                link = 'http://imdb.com' + a.get('href').replace('/?ref_=wl_li_tt','')
                entry = Entry()
                entry['title'] = a.string
                entry['url'] = link
                entry['imdb_id'] = extract_id(link)
                entry['imdb_name'] = a.string
                entries.append(entry)
        return entries

@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2)
