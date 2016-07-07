from __future__ import unicode_literals, division, absolute_import

import hashlib
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote_plus

import re
import logging

from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('fuzer')

CATEGORIES = {
    'all': 0,

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
            'user_id': {'type': 'integer'},
            'rss_key': {'type': 'string'},
            'category': {
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]
            },
        },
        'required': ['username', 'password', 'user_id', 'rss_key'],
        'additionalProperties': False
    }

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
        Search for name from fuzer.
        """
        rss_key = config['rss_key']
        username = config['username']
        password = hashlib.md5(config['password']).hexdigest()

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
            raise PluginError('Could not connect to fuzer: %s', str(e))

        category = config.get('category', 0)
        # Make sure categories is a list

        # If there are any text categories, turn them into their id number
        category = category if isinstance(category, int) else CATEGORIES[category]

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string).replace(":", "")
            text = quote_plus(query.encode('windows-1255'))
            url = 'https://www.fuzer.me/index.php?name=torrents&text={}&category={}&search=%E7%F4%F9'.format(text,
                                                                                                             category)
            log.debug('Using %s as fuzer search url' % url)

            page = requests.get(url, cookies=login.cookies).content
            soup = get_soup(page)

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

                entry['title'] = title
                final_url = 'https://www.fuzer.me/rss/torrent.php/{}/{}/{}/{}.torrent'.format(attachment_id,
                                                                                              config['user_id'],
                                                                                              rss_key, title)

                log.debug('RSS-ified download link: %s' % final_url)
                entry['url'] = final_url

                size_pos = 4 if 'stickytr' in tr.get('class', []) else 3
                seeders_pos = 6 if 'stickytr' in tr.get('class', []) else 5
                leechers_pos = 7 if 'stickytr' in tr.get('class', []) else 6

                seeders = int(tr.find_all('td')[seeders_pos].find('div').text)
                leechers = int(tr.find_all('td')[leechers_pos].find('div').text)

                entry['torrent_seeds'] = seeders
                entry['torrent_leeches'] = leechers
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])

                # use tr object for size
                size_text = tr.find_all('td')[size_pos].find('div').text.strip()
                size = re.search('(\d+.?\d+)([TGMK]?)B', size_text)
                if size:
                    if size.group(2) == 'T':
                        entry['content_size'] = int(float(size.group(1)) * 1000 ** 4 / 1024 ** 2)
                    elif size.group(2) == 'G':
                        entry['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                    elif size.group(2) == 'M':
                        entry['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                    elif size.group(2) == 'K':
                        entry['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)
                    else:
                        entry['content_size'] = int(float(size.group(1)) / 1024 ** 2)
                entries.add(entry)

        return sorted(entries, reverse=True, key=lambda x: x.get('search_sort'))


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteFuzer, 'fuzer', groups=['search'], api_ver=2)
