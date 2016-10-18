from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session, get, TimedLimiter, RequestException
from flexget.utils.search import normalize_scene

log = logging.getLogger('yify')

requests = Session()

CATEGORIES = {
    'all': 0,

    # Movies
    'x264': 17,
    'x264 720p': 45,
    'x264 1080p': 44,
    'x264 3D': 47,
    'XviD': 14,
    'XviD 720p': 48,
    'Full BD': 42,

    # TV
    'HDTV': 41,
    'SDTV': 18,

    # Adult
    'XXX': 4,

    # Music
    'MusicMP3': 23,
    'MusicFLAC':25,

    # Games
    'Games/PC ISO': 27,
    'Games/PC RIP': 28,
    'Games/PS3': 40,
    'Games/XBOX-360': 32,
    'Software/PC ISO':33,

    # E-Books
    'e-Books': 35
}


class SearchYIFY(object):
    """
        RarBG search plugin.

        To perform search against single category:

        rarbg:
            category: x264 720p

        To perform search against multiple categories:

        rarbg:
            category:
                - x264 720p
                - x264 1080p

        Movie categories accepted: x264 720p, x264 1080p, XviD, Full BD
        TV categories accepted: HDTV, SDTV

        You can use also use category ID manually if you so desire (eg. x264 720p is actually category id '45')
    """

    schema = {
        'type': 'boolean'
    }

    base_url = 'https://yts.ag/api/v2/list_movies.json'

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on RarBG
        """
        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):
            log.debug(entry.get('rubish'))

            params = {
                'query_term': entry.get('imdb_id')
            }

            try:
                page = requests.get(self.base_url, params=params)
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('YIFY request failed: %s' % e.args[0])
                continue           
           
            r = page.json()

            if 'movies' in r.get('data'):
                movies = r['data']['movies']
                print movies
                
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchYIFY, 'yify', groups=['search'], api_ver=2)
