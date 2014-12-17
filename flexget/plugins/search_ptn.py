from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.imdb import extract_id
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability

log = logging.getLogger('search_ptn')

session = requests.Session()

categories = {
    '1080p': 'c5',
    '720p': 'c6',
    'bdrip': 'c10',
    'bluray': 'c1',
    'brrip': 'c11',
    'dvdr': 'c4',
    'dvdrip': 'c12',
    'mp4': 'c16',
    'ost/flac': 'c17',
    'ost/mp3': 'c18',
    'packs': 'c20',
    'r5/scr': 'c13',
    'remux': 'c2',
    'tvrip': 'c15',
    'webrip': 'c14'
}


class SearchPTN(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'login_key': {'type': 'string'},
            'password': {'type': 'string'},
            'categories': {
                'type': 'array',
                'items': {'type': 'string', 'enum': list(categories)}
            }
        },
        'required': ['username', 'login_key', 'password'],
        'additionalProperties': False
    }

    def search(self, task, entry, config):
        if not session.cookies:
            try:
                login_params = {'username': config['username'],
                                'password': config['password'],
                                'loginkey': config['login_key']}
                session.post('https://piratethenet.org/takelogin.php', data=login_params, verify=False)
            except requests.RequestException as e:
                log.error('Error while logging in to PtN: %s', e)

        # Default to searching by title (0=title 3=imdb_id)
        search_by = 0
        if 'imdb_id' in entry:
            searches = [entry['imdb_id']]
            search_by = 3
        elif 'movie_name' in entry:
            search = entry['movie_name']
            if 'movie_year' in entry:
                search += ' %s' % entry['movie_year']
            searches = [search]
        else:
            searches = entry.get('search_strings', [entry['title']])

        params = {'_by': search_by}
        if config.get('categories'):
            for cat in config['categories']:
                params[categories[cat]] = 1
        results = set()
        for search in searches:
            params['search'] = search
            try:
                r = session.get('http://piratethenet.org/browse.php', params=params)
            except requests.RequestException as e:
                log.error('Error searching ptn: %s' % e)
                continue
            soup = get_soup(r.text)
            if 'login' in soup.head.title.text.lower():
                log.error('PtN cookie info invalid')
                raise plugin.PluginError('PTN cookie info invalid')
            links = soup.findAll('a', attrs={'href': re.compile('download\.php\?torrent=\d+')})
            for row in [l.find_parent('tr') for l in links]:
                entry = Entry()
                td = row.findAll('td')
                entry['title'] = row.find('a', attrs={'href': re.compile('details\.php\?id=\d+')}).text
                entry['imdb_id'] = extract_id(row.find('a', attrs={'href': re.compile('imdb\.com')}).get('href'))
                dl_href = row.find('a', attrs={'href': re.compile('download\.php\?torrent=\d+')}).get('href')
                passkey = re.findall('passkey=([\d\w]*)"', r.text)[0]
                entry['url'] = 'http://piratethenet.org/' + dl_href + '&passkey=' + passkey
                # last two table cells contains amount of seeders and leeechers respectively
                s, l = td[-2:]
                entry['torrent_seeds'] = int(s.text)
                entry['torrent_leeches'] = int(l.text)
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                # 4th last table cell contains size, of which last two symbols are unit
                size = td[-4].text[:-2]
                unit = td[-4].text[-2:]
                if unit == 'GB':
                    entry['content_size'] = int(float(size) * 1024)
                elif unit == 'MB':
                    entry['content_size'] = int(float(size))
                elif unit == 'KB':
                    entry['content_size'] = int(float(size) / 1024)
                results.add(entry)
        return results


@event('plugin.register')
def register_plugin():
    plugin.register(SearchPTN, 'ptn', groups=['search'], api_ver=2)
