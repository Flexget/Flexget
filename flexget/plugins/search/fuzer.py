# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import

import hashlib
from builtins import *  # pylint: disable=unused-import, redefined-builtin
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

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search for name from fuzer.
        """
        rss_key = config['rss_key']
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

        user_id = requests.cookies.get('fzr2userid')
        category = config.get('category', [0])
        # Make sure categories is a list
        if not isinstance(category, list):
            category = [category]

        # If there are any text categories, turn them into their id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in category]
        params = {'name': 'torrents',
                  'category': '0',
                  'search': '%E7%F4%F9'}

        for i in range(len(categories)):
            params.update({"c{}".format(i + 1): categories[i]})

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string).replace(":", "")
            text = quote_plus(query.encode('windows-1255'))

            page = requests.get('https://www.fuzer.me/index.php?text={}'.format(text), params=params,
                                cookies=login.cookies)
            log.debug('Using %s as fuzer search url' % page.url)
            soup = get_soup(page.content)

            table = soup.find('tbody', {'id': 'collapseobj_module_17'})
            if not table:
                log.debug('No search results were returned, continuing')
                continue
            for tr in table.find_all("tr"):
                name = tr.find("a", {'href': re.compile('https:\/\/www.fuzer.me\/showthread\.php\?t=\d+')})
                if not name:
                    continue
                result = re.search('\|\s(.*)', name.text)
                title = result.group(1) if result else name.text
                title = title.replace(' ', '.')
                link = tr.find("a", attrs={'href': re.compile('attachmentid')}).get('href')
                attachment_id = re.search('attachmentid\=(\d+)', link).group(1)

                e = Entry()
                e['title'] = title
                final_url = 'https://www.fuzer.me/rss/torrent.php/{}/{}/{}/{}.torrent'.format(attachment_id, user_id,
                                                                                              rss_key, title)

                log.debug('RSS-ified download link: %s' % final_url)
                e['url'] = final_url

                size_pos = 4 if 'stickytr' in tr.get('class', []) else 3
                seeders_pos = 6 if 'stickytr' in tr.get('class', []) else 5
                leechers_pos = 7 if 'stickytr' in tr.get('class', []) else 6

                seeders = int(tr.find_all('td')[seeders_pos].find('div').text)
                leechers = int(tr.find_all('td')[leechers_pos].find('div').text)

                e['torrent_seeds'] = seeders
                e['torrent_leeches'] = leechers
                e['search_sort'] = torrent_availability(e['torrent_seeds'], e['torrent_leeches'])

                # use tr object for size
                size_text = tr.find_all('td')[size_pos].find('div').text.strip()
                size = re.search('(\d+.?\d+)([TGMK]?)B', size_text)
                if size:
                    if size.group(2) == 'T':
                        e['content_size'] = int(float(size.group(1)) * 1000 ** 4 / 1024 ** 2)
                    elif size.group(2) == 'G':
                        e['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                    elif size.group(2) == 'M':
                        e['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                    elif size.group(2) == 'K':
                        e['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)
                    else:
                        e['content_size'] = int(float(size.group(1)) / 1024 ** 2)
                entries.add(e)

        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteFuzer, 'fuzer', groups=['search'], api_ver=2)
