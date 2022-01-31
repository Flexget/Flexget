from urllib.parse import urlencode
from xml.etree import ElementTree

from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.requests import RequestException

logger = logger.bind(name='torznab')


class Torznab:
    """Torznab search plugin

    Handles searching for tv shows and movies, with fallback to simple query strings if these are not available.
    """

    @property
    def schema(self):
        """The schema of the plugin"""
        schema = {
            'type': 'object',
            'properties': {
                'apikey': {'type': 'string'},
                'categories': {'type': 'array', 'items': {'type': 'integer'}, 'default': []},
                'searcher': {
                    'type': 'string',
                    'enum': ['movie', 'tv', 'tvsearch', 'search'],
                    'default': 'search',
                },
                'website': {'type': 'string', 'format': 'url'},
            },
            'required': ['website', 'apikey'],
            'additionalProperties': False,
        }
        return schema

    def search(self, task, entry, config=None):
        """Search interface"""
        self._setup(task, config)
        params = {}
        if self.params['t'] == 'movie':
            params = self._convert_query_parameters(entry, ['imdbid'])
        elif self.params['t'] == 'tvsearch':
            params = self._convert_query_parameters(
                entry, ['rid', 'tvdbid', 'traktid', 'tvmazeid', 'imdbid', 'tmdbid', 'season', 'ep']
            )

        if 'q' not in params.keys():
            query = entry['title']
        else:
            query = params['q']

        entries = []
        for search_string in entry.get('search_strings', [query]):
            params['q'] = search_string
            results = self.create_entries_from_query(self._build_url(**params), task)
            entries.extend(results)
        return entries

    def _build_url(self, **kwargs):
        """Builds the url with query parameters from the arguments"""
        params = self.params.copy()
        params.update(kwargs)
        logger.debug('Configured parameters: {}', params)
        url = '{}/api?'.format(self.base_url)
        url = '{}{}'.format(url, urlencode(params))
        return url

    def _setup(self, task, config):
        """Set up parameters"""
        self.base_url = config['website'].rstrip('/')
        self.supported_params = []
        if config['searcher'] == 'tv':
            config['searcher'] = 'tvsearch'

        self.params = {'apikey': config['apikey'], 'extended': 1}

        logger.debug('Config: {}', config)
        self._setup_caps(task, config['searcher'], config['categories'])

    @plugin.internet(logger)
    def _setup_caps(self, task, searcher, categories):
        """Gets the capabilities of the torznab indexer and matches it with the provided configuration"""

        response = task.requests.get(self._build_url(t='caps'))
        logger.debug('Raw caps response {}', response.content)
        root = ElementTree.fromstring(response.content)
        self._setup_searcher(root, searcher, categories)

    def _setup_searcher(self, xml_root, searcher, categories):
        """Gets the available searchers (tv, movie, etc) for the indexer and their supported parameters"""
        aliases = {'movie': 'movie-search', 'search': 'search', 'tvsearch': 'tv-search'}

        searchers = {item.tag: item.attrib for item in list(xml_root.find('searching'))}
        if searchers:
            if self._check_searcher(searchers, aliases[searcher]):
                self.supported_params = searchers[aliases[searcher]]['supportedParams'].split(',')
                self.params['t'] = searcher
                logger.debug(
                    "Searcher '{}' set up with '{}' parameters",
                    aliases[searcher],
                    self.supported_params,
                )
                if searcher != 'search':
                    self._setup_categories(xml_root, categories)
            elif searcher != 'search' and self._check_searcher(searchers, 'search'):
                logger.warning(
                    "'{}' searcher not available, falling back to 'search'.", aliases[searcher]
                )
                self.supported_params = searchers['search']['supportedParams'].split(',')
                self.params['t'] = 'search'
                logger.debug(
                    "Searcher '{}' set up with '{}' parameters",
                    aliases[searcher],
                    self.supported_params,
                )
            else:
                raise PluginError('No searcher available on {}'.format(self.base_url))
        else:
            raise PluginError('No searcher available on {}'.format(self.base_url))

    def _check_searcher(self, searchers, searcher):
        """Check if the given searchers is in the list, available and has supported params"""
        return (
            searcher in searchers.keys()
            and searchers[searcher]['available'] == 'yes'
            and searchers[searcher]['supportedParams']
        )

    def _setup_categories(self, xml_root, categories):
        """Gets the available search categories for the indexer"""
        if self.params['t'] == 'movie':
            category_range = range(2000, 3000)
        elif self.params['t'] == 'tvsearch':
            category_range = range(5000, 6000)
        used_categories = []
        for category in xml_root.findall('categories//*[@id][@name]'):
            try:
                category_id = int(category.attrib['id'])
                if category_id in category_range and category_id not in used_categories:
                    if categories:
                        if category_id in categories:
                            used_categories.append(category_id)
                    else:
                        used_categories.append(category_id)
            except ValueError:
                continue
        if used_categories:
            logger.debug('Setting search categories to {}', used_categories)
            self.params['cat'] = ','.join(str(e) for e in used_categories)

    @plugin.internet(logger)
    def create_entries_from_query(self, url, task):
        """Fetch feed and fill entries from"""

        logger.info('Fetching URL: {}', url)

        try:
            response = task.requests.get(url)
        except RequestException as e:
            raise PluginError("Failed fetching '{}': {}".format(url, e))

        entries = []
        root = ElementTree.fromstring(response.content)
        for item in root.findall('.//item'):
            entry = Entry()
            enclosure = item.find("enclosure[@type='application/x-bittorrent']")
            if enclosure is None:
                logger.warning(
                    "Item '{}' does not contain a bittorent enclosure.", item.title.string
                )
                continue
            else:
                entry['url'] = enclosure.attrib['url']
                try:
                    entry['content_size'] = int(enclosure.attrib['length']) // (2**20)
                except ValueError:
                    entry['content_size'] = 0
                entry['type'] = enclosure.attrib['type']

            ns = {'torznab': 'http://torznab.com/schemas/2015/feed'}
            self._parse_torznab_attrs(entry, item.findall('torznab:attr', ns))

            for child in item.iter():
                if child.tag in ['{http://torznab.com/schemas/2015/feed}attr', 'enclosure']:
                    continue
                else:
                    if child.tag in ['description', 'title'] and child.text:
                        entry[child.tag] = child.text
            entries.append(entry)
        return entries

    def _parse_torznab_attrs(self, entry, attrs):
        """Parse the torznab::attr values from the response

        https://github.com/Sonarr/Sonarr/wiki/Implementing-a-Torznab-indexer#torznab-results
        """
        dictionary = {
            'episode': {'name': 'series_episode', 'type': int},
            'imdbid': {'name': 'imdb_id', 'type': str},
            'infohash': {'name': 'torrent_info_hash', 'type': str},
            'leechers': {'name': 'torrent_leeches', 'type': int},
            'rageid': {'name': 'tvrage_id', 'type': int},
            'season': {'name': 'series_season', 'type': int},
            'seeders': {'name': 'torrent_seeds', 'type': int},
            'title': {'name': 'series_name', 'type': str},
            'tmdbid': {'name': 'tmdb_id', 'type': int},
            'traktid': {'name': 'trakt_id', 'type': int},
            'tvdbid': {'name': 'tvdb_id', 'type': int},
            'tvmazeid': {'name': 'tvmaze_series_id', 'type': int},
            'tvrageid': {'name': 'tvrage_id', 'type': int},
        }
        misc = {}
        for attr in attrs:
            name = attr.get('name')
            if name in dictionary.keys():
                entry[dictionary[name]['name']] = dictionary[name]['type'](attr.get('value'))
            elif name == 'peers':
                misc['peers'] = int(attr.get('value'))
            elif name == 'imdb':
                misc['imdb'] = str(attr.get('value'))
            elif name == 'size':
                misc['size'] = int(attr.get('value'))

        if 'imdb_id' not in entry.keys() and 'imdb' in misc.keys():
            entry['imdb_id'] = 'tt{}'.format(misc['imdb'])

        if 'peers' in misc.keys():
            if 'torrent_leeches' not in entry.keys() and 'torrent_seeds' in entry.keys():
                entry['torrent_leeches'] = misc['peers'] - entry['torrent_seeds']
            if 'torrent_leeches' in entry.keys() and 'torrent_seeds' not in entry.keys():
                entry['torrent_seeds'] = misc['peers'] - entry['torrent_leeches']

        if 'content_size' not in entry.keys() and 'size' in misc.keys():
            entry['content_size'] = misc['size'] // (2**20)

        if 'torrent_seeds' in entry.keys() and 'torrent_leeches' in entry.keys():
            entry['torrent_availability'] = torrent_availability(
                entry['torrent_seeds'], entry['torrent_leeches']
            )

    def _convert_query_parameters(self, entry, fields):
        """Convert from Flexget fields to query parameters for torznab.

        https://flexget.com/Entry
        https://github.com/nZEDb/nZEDb/blob/0.x/docs/newznab_api_specification.txt#L441
        """
        params = {}
        dictionary = {
            'rid': 'tvrage_id',
            'tvdbid': 'tvdb_id',
            'traktid': 'trakt_show_id',
            'tvmazeid': 'tvmaze_series_id',
            'imdbid': 'imdb_id',
            'tmdbid': 'tmdb_id',
            'season': 'series_season',
            'ep': 'series_episode',
        }

        for k, v in dictionary.items():
            if k not in self.supported_params or k not in fields:
                continue
            if v in entry.keys() and entry[v]:
                params[k] = entry[v]
        for k in [
            'tvdb_series_name',
            'trakt_series_name',
            'tvmaze_series_name',
            'imdb_name',
            'series_name',
        ]:
            if k in entry.keys() and entry[k]:
                params['q'] = entry[k]
                break

        return params


@event('plugin.register')
def register_plugin():
    plugin.register(Torznab, 'torznab', api_ver=2, interfaces=['search'])
