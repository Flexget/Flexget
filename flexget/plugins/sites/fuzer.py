# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import

import hashlib
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote_plus

import re
import logging

from requests.exceptions import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import Session as RequestSession
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode
from flexget.utils.tools import parse_filesize

log = logging.getLogger('fuzer')

requests = RequestSession()

CATEGORIES = {
    # Movies
    'HD Movies': 9,
    'XviD': 7,
    'BRRip': 59,
    'Israeli HD Movies': 61,
    'Israeli Movies': 60,
    'DVDR': 58,
    'Dubbed Movies': 83,

    # TV
    'HD Shows': 10,
    'Shows': 8,
    'Israeli HD Shows': 63,
    'Israeli Shows': 62,
    'Dubbed Shows': 84,

    # Anime
    'Anime': 65,

    # FuzePacks
    'Movie Packs': 73,
    'Shows Packs': 76
}


class UrlRewriteFuzer(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'rss_key': {'type': 'string'},
            'category': one_or_more(
                {'oneOf': [
                    {'type': 'string', 'enum': list(CATEGORIES)},
                    {'type': 'integer'}
                ]}),
        },
        'required': ['username', 'password', 'rss_key'],
        'additionalProperties': False
    }

    @staticmethod
    def get_fuzer_soup(search_term, categories_list):
        params = {'matchquery': 'any'}
        page = requests.get(
            'https://www.fuzer.me/browse.php?ref_=advanced&query={}&{}'.format(search_term, '&'.join(categories_list)),
            params=params)
        log.debug('Using %s as fuzer search url' % page.url)
        return get_soup(page.content)

    def extract_entry_from_soup(self, soup):
        table = soup.find('div', {'id': 'main_table'})
        if table is None:
            raise PluginError('Could fetch results table from Fuzer, aborting')
        table = table.find('table', {'class': 'table_info'})
        if len(table.find_all('tr')) == 1:
            log.debug('No search results were returned, continuing')
            return []
        entries = []
        for tr in table.find_all("tr"):
            if not tr.get('class') or 'colhead_dark' in tr.get('class'):
                continue
            name = tr.find('div', {'class': 'main_title'}).find('a').text
            torrent_name = re.search('\\r\\n(.*)',
                                     tr.find('div', {'style': 'float: right;'}).find('a')['title']).group(1)
            attachment_link = tr.find('div', {'style': 'float: right;'}).find('a')['href']
            attachment_id = re.search('attachmentid\=(\d+)', attachment_link).group(1)
            raw_size = tr.find_all('td', {'class': 'inline_info'})[0].text.strip()
            seeders = int(tr.find_all('td', {'class': 'inline_info'})[2].text)
            leechers = int(tr.find_all('td', {'class': 'inline_info'})[3].text)

            e = Entry()
            e['title'] = name
            final_url = 'https://www.fuzer.me/rss/torrent.php/{}/{}/{}/{}'.format(attachment_id, self.user_id,
                                                                                  self.rss_key, torrent_name)

            log.debug('RSS-ified download link: %s' % final_url)
            e['url'] = final_url

            e['torrent_seeds'] = seeders
            e['torrent_leeches'] = leechers
            e['search_sort'] = torrent_availability(e['torrent_seeds'], e['torrent_leeches'])

            size = re.search('(\d+(?:[.,]\d+)*)\s?([KMGTP]B)', raw_size)
            e['content_size'] = parse_filesize(size.group(0))

            entries.append(e)
        return entries

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search for name from fuzer.
        """
        self.rss_key = config['rss_key']
        username = config['username']
        password = hashlib.md5(config['password'].encode('utf-8')).hexdigest()

        # build the form request:
        data = {'cookieuser': '1',
                'do': 'login',
                's': '',
                'securitytoken': 'guest',
                'vb_login_username': username,
                'vb_login_password': '',
                'vb_login_md5password': password,
                'vb_login_md5password_utf': password
                }
        # POST the login form:
        try:
            login = requests.post('https://www.fuzer.me/login.php?do=login', data=data)
        except RequestException as e:
            raise PluginError('Could not connect to fuzer: %s' % str(e))

        login_check_phrases = ['ההתחברות נכשלה', 'banned']
        if any(phrase in login.text for phrase in login_check_phrases):
            raise PluginError('Login to Fuzer failed, check credentials')

        self.user_id = requests.cookies.get('fzr2userid')
        category = config.get('category', [0])
        # Make sure categories is a list
        if not isinstance(category, list):
            category = [category]

        # If there are any text categories, turn them into their id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in category]

        c_list = []
        for c in categories:
            c_list.append('c{}={}'.format(quote_plus('[]'), c))

        entries = []
        if entry.get('imdb_id'):
            log.debug('imdb_id {} detected, using in search.'.format(entry['imdb_id']))
            soup = self.get_fuzer_soup(entry['imdb_id'], c_list)
            entries = self.extract_entry_from_soup(soup)
            if entries:
                for e in list(entries):
                    e['imdb_id'] = entry.get('imdb_id')
        else:
            for search_string in entry.get('search_strings', [entry['title']]):
                query = normalize_unicode(search_string).replace(":", "")
                text = quote_plus(query.encode('windows-1255'))
                soup = self.get_fuzer_soup(text, c_list)
                entries += self.extract_entry_from_soup(soup)
        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort')) if entries else []


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteFuzer, 'fuzer', groups=['search'], api_ver=2)
