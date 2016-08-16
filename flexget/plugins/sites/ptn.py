from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.imdb import extract_id
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability
from flexget.utils.tools import parse_filesize

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

default_search_params = {
    # 'searchstring': 'search term',
    # 'advancedsearchparameters': '[year=1999]',
    'sort': 'browsedate',
    'skw': 'showall',
    'compression': 'unraredonly',
    'packs': 'torrentsonly',
    'titleonly': 'true',
    'subscriptions': 'showall',
    'visibility': 'aliveonly',
    'visiblecategories': 'Action,Adventure,Animation,Biography,Comedy,Crime,Documentary,Drama,Eastern,Family,Fantasy,'
                         'History,Holiday,Horror,Kids,Musical,Mystery,Romance,Sci-Fi,Short,Sports,Thriller,War,Western',
    'hiddenqualities': 'FLAC,MP3',
    'order': 'DESC',
    'action': 'torrentstable',
    'bookmarks': 'showall',
    'viewtype': 1,
    'page': 1
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
                'items': {'type': 'string', 'enum': list(categories)},
                'deprecated': 'PtN category filtering is broken. Someone open a PR!'
            }
        },
        'required': ['username', 'login_key', 'password'],
        'additionalProperties': False
    }

    def create_entries(self, soup, passkey=None, imdb_id=None):
        entries = []
        links = soup.findAll('a', attrs={'href': re.compile('download\.php\?torrent=\d+')})
        rows = [l.find_parent('tr') for l in links]
        for row in rows:
            entry = Entry()
            entry['title'] = row.find('a', attrs={'href': re.compile('detail\.php\?id')}).text
            dl_href = row.find('a', attrs={'href': re.compile('download\.php\?torrent=\d+')}).get('href')
            entry['url'] = 'http://piratethenet.org/' + dl_href + '&passkey=' + passkey
            entry['torrent_seeds'] = int(row.find(title='Number of Seeders').text)
            entry['torrent_leeches'] = int(row.find(title='Number of Leechers').text)
            entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])

            entry['content_size'] = parse_filesize(str(row.find(title='Torrent size').text), si=False)

            if imdb_id:
                entry['imdb_id'] = imdb_id
            entries.append(entry)
        return entries

    def search(self, task, entry, config):
        if not session.cookies or not session.passkey:
            try:
                login_params = {'username': config['username'],
                                'password': config['password'],
                                'loginkey': config['login_key']}
                r = session.post('https://piratethenet.org/takelogin.php', data=login_params, verify=False)
            except requests.RequestException as e:
                log.error('Error while logging in to PtN: %s', e)
                raise plugin.PluginError('Could not log in to PtN')

            # Sorty hacky, we'll just store the passkey on the session
            passkey = re.search('passkey=([\d\w]+)"', r.text)
            if passkey:
                session.passkey = passkey.group(1)
            else:
                log.error('PtN cookie info invalid')
                raise plugin.PluginError('PTN cookie info invalid')

        search_params = default_search_params.copy()
        if 'movie_name' in entry:
            if 'movie_year' in entry:
                search_params['advancedsearchparameters'] = '[year=%s]' % entry['movie_year']
            searches = [entry['movie_name']]
        else:
            searches = entry.get('search_strings', [entry['title']])

        results = set()
        for search in searches:
            search_params['searchstring'] = search
            try:
                r = session.get('http://piratethenet.org/torrentsutils.php', params=search_params)
            except requests.RequestException as e:
                log.error('Error searching ptn: %s' % e)
                continue
            # html5parser doesn't work properly for some reason
            soup = get_soup(r.text, parser='html.parser')
            for movie in soup.select('.torrentstd'):
                imdb_id = movie.find('a', href=re.compile('.*imdb\.com/title/tt'))
                if imdb_id:
                    imdb_id = extract_id(imdb_id['href'])
                if imdb_id and 'imdb_id' in entry and imdb_id != entry['imdb_id']:
                    continue
                results.update(self.create_entries(movie, passkey=session.passkey, imdb_id=imdb_id))

        return results


@event('plugin.register')
def register_plugin():
    plugin.register(SearchPTN, 'ptn', groups=['search'], api_ver=2)
