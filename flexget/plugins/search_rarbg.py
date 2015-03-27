from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.requests import Session
from flexget.utils.search import normalize_unicode

log = logging.getLogger('rarbg')

requests = Session()
requests.set_domain_delay('torrentapi.org', '10.3 seconds')  # they only allow 1 request per 10 seconds

CATEGORIES = {
    'all': 0,

    # Movies
    'x264 720p': 45,
    'x264 1080p': 44,
    'XviD': 14,
    'Full BD': 42,

    # TV
    'HDTV': 41,
    'SDTV': 18
}


class SearchRarBG(object):
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
        'type': 'object',
        'properties': {
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]}),
            'sorted_by': {'type': 'string', 'enum': ['seeders', 'leechers', 'last'], 'default': 'last'},
            # min_seeders and min_leechers do not seem to work
            # 'min_seeders': {'type': 'integer', 'default': 0},
            # 'min_leechers': {'type': 'integer', 'default': 0},
            'limit': {'type': 'integer', 'enum': [25, 50, 100], 'default': 25},
            'ranked': {'type': 'boolean', 'default': True}
        },
        "additionalProperties": False
    }

    base_url = 'https://torrentapi.org/pubapi.php'

    def get_token(self):
        # using rarbg.com to avoid the domain delay as tokens can be requested always
        r = requests.get('https://rarbg.com/pubapi/pubapi.php', params={'get_token': 'get_token', 'format': 'json'})
        token = None
        try:
            token = r.json().get('token')
        except ValueError:
            log.error('Could not retrieve RARBG token.')
        log.debug('RarBG token: %s' % token)
        return token

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on RarBG
        """

        categories = config.get('category', 'all')
        # Ensure categories a list
        if not isinstance(categories, list):
            categories = [categories]
        # Convert named category to its respective category id number
        categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
        category_url_fragment = urllib.quote(';'.join(str(c) for c in categories))

        entries = set()

        token = self.get_token()
        if not token:
            log.error('No token set. Exiting RARBG search.')
            return entries

        params = {'mode': 'search', 'token': token, 'ranked': int(config['ranked']),
                  # 'min_seeders': config['min_seeders'], 'min_leechers': config['min_leechers'],
                  'sort': config['sorted_by'], 'category': category_url_fragment, 'format': 'json'}

        for search_string in entry.get('search_strings', [entry['title']]):
            params.pop('search_string', None)
            params.pop('search_imdb', None)

            if entry.get('movie_name'):
                params['search_imdb'] = entry.get('imdb_id')
            else:
                query = normalize_unicode(search_string)
                query_url_fragment = query.encode('utf8')
                params['search_string'] = query_url_fragment

            page = requests.get(self.base_url, params=params)

            try:
                r = page.json()
            except ValueError:
                log.debug(page.text)
                break

            for result in r:
                entry = Entry()

                entry['title'] = result.get('f')

                entry['url'] = result.get('d')

                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchRarBG, 'rarbg', groups=['search'], api_ver=2)
