from __future__ import unicode_literals, division, absolute_import
import logging

from requests.auth import AuthBase

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.imdb import extract_id
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability

session = requests.Session()
log = logging.getLogger('search_ptn')


class PtNAuth(AuthBase):
    def __init__(self, cookies):
        self.cookies = cookies

    def __call__(self, r):
        r.prepare_cookies(self.cookies)
        return r


class SearchPTN(object):
    schema = {
        'type': 'object',
        'properties': {
            'hashv': {'type': 'string'},
            'pass': {'type': 'string'},
            'uid': {'type': 'number'}
        },
        'required': ['hashv', 'pass', 'uid'],
        'additionalProperties': False
    }

    def search(self, entry, config):
        cookies = {
            'ptn_hashv': config['hashv'],
            'ptn_pass': config['pass'],
            'ptn_uid': str(config['uid'])
        }

        download_auth = PtNAuth(cookies)
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

        results = set()
        for search in searches:
            try:
                r = requests.get('http://piratethenet.org/browse.php',
                                 params={'search': search, '_by': search_by}, cookies=cookies)
            except requests.RequestException as e:
                log.error('Error searching ptn: %s' % e)
                continue
            soup = get_soup(r.text)
            if 'login' in soup.head.title.text.lower():
                log.error('PtN cookie info invalid')
                raise plugin.PluginError('PTN cookie info invalid')
            try:
                results_table = soup.find_all('table', attrs={'class': 'main'}, limit=2)[1]
            except IndexError:
                log.debug('no results found for `%s`' % search)
                continue
            for row in results_table.find_all('tr')[1:]:
                columns = row.find_all('td')
                entry = Entry()
                links = columns[1].find_all('a', recursive=False, limit=2)
                entry['title'] = links[0].text
                if len(links) > 1:
                    entry['imdb_id'] = extract_id(links[1].get('href'))
                entry['url'] = 'http://piratethenet.org/' + columns[2].a.get('href')
                entry['download_auth'] = download_auth
                entry['torrent_seeds'] = int(columns[8].text)
                entry['torrent_leeches'] = int(columns[9].text)
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                size = columns[6].find('br').previous_sibling
                unit = columns[6].find('br').next_sibling
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
