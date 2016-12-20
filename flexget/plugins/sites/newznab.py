from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote_plus

import re
import logging
import feedparser
from xml.dom import minidom
from datetime import datetime, timedelta, date, time

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.tools import parse_timedelta, split_title_year, value_to_int, find_value, value_to_naive_utc
from flexget.utils.search import normalize_unicode
from flexget.utils.template import RenderError

__author__ = 'andy (org. by deksan)'

log = logging.getLogger('newznab')

CATEGORIES = {
    # Games Consoles
    'game': 1000,
    'game/nds': 1010,
    'game/psp': 1020,
    'game/wii': 1030,
    'game/xbox': 1040,
    'game/xbox360': 1050,
    'game/wiiware': 1060,
    'game/xbox360dlc': 1070,
    'game/ps3': 1080,
    'game/xbox-one': 1090,  # unofficial
    'game/ps4': 1100,  # unofficial
    # Movie
    'movie': 2000,
    'movie/foreign': 2010,
    'movie/other': 2020,
    'movie/sd': 2030,
    'movie/hd': 2040,
    'movie/uhd': 2045,  # unofficial
    'movie/bluray': 2050,
    'movie/3d': 2060,
    'movie/dvd': 2070,
    'movie/web-dl': 2080,  # unofficial
    # Music
    'music': 3000,
    'music/mp3': 3010,
    'music/video': 3020,
    'music/audiobook': 3030,
    'music/lossless': 3040,
    'music/foreign': 3060,  # unofficial
    # PC (Games + Software)
    'pc': 4000,
    'pc/0day': 4010,
    'pc/iso': 4020,
    'pc/mac': 4030,
    'pc/mobile-other': 4040,
    'pc/games': 4050,
    'pc/mobile-ios': 4060,
    'pc/mobile-android': 4070,
    # TV
    'tv': 5000,
    'tv/web-dl': 5010,  # unofficial
    'tv/foreign': 5020,
    'tv/sd': 5030,
    'tv/hd': 5040,
    'tv/uhd': 5045,  # unofficial
    'tv/other': 5050,
    'tv/sport': 5060,
    'tv/anime': 5070,
    'tv/documentary': 5080,  # unofficial
    # XXX
    'xxx': 6000,
    'xxx/dvd': 6010,
    'xxx/wmv': 6020,
    'xxx/xvid': 6030,
    'xxx/x264': 6040,
    'xxx/uhd': 6045,  # unofficial
    'xxx/pack': 6050,
    'xxx/imageset': 6060,
    'xxx/packs': 6070,  # unofficial
    'xxx/sd': 6080,  # unofficial
    'xxx/web-dl': 6090,  # unofficial
    # Misc
    'misc': 7000,
    'misc/misc': 7010,
    'misc/ebook': 7020,
    'misc/comics': 7030,
    # Unknown
    'not-determined': 7900
}

field_map = {
    'title': 'title',
    'url': 'link',
    'newznab_pubdate': lambda xml: value_to_naive_utc(find_value(['updated_parsed', 'updated'], xml)),
    'newznab_grabs': lambda xml: value_to_int(find_value('newznab_grabs.value', xml)),
    'newznab_size': lambda xml: value_to_int(find_value('newznab_size.value', xml)),
    'newznab_files': lambda xml: value_to_int(find_value('newznab_files.value', xml)),
    'newznab_usenet_date': lambda xml: value_to_naive_utc(find_value('newznab_usenetdate.value', xml)),
    'newznab_password': lambda xml: value_to_int(find_value('newznab_password.value', xml)),
    'newznab_guid': lambda xml: re.split(r'[/=]', find_value(['id', 'guid'], xml, default='')).pop(),
    'newznab_usenet_group': 'newznab_group.value',
    'newznab_tvairdate': lambda xml: value_to_naive_utc(find_value('newznab_tvairdate.value', xml)),
    'newznab_season':
        lambda xml: value_to_int(find_value('newznab_season.value', xml, regex=r'[Ss]([0-9]{1,2})')),
    'newznab_episode':
        lambda xml: value_to_int(find_value('newznab_episode.value', xml, regex=r'[Ee]([0-9]{1,3})')),
    'newznab_hydra_indexer_name': 'newznab_hydraindexername.value',
    'newznab_hydra_indexer_host': 'newznab_hydraindexerhost.value',
    'newznab_hydra_indexer_score': lambda xml: value_to_int(find_value('newznab_hydraindexerscore.value', xml))
}

field_validation_list = [
    'title',
    'url'
]

PLUGIN_LOOKUP_MAP = {
    'tvdb': 'thetvdb_lookup',
    'trakt': 'trakt_lookup',
    'tvmaze': 'tvmaze_lookup',
    'imdb': 'imdb_lookup',
    'tmdb': 'tmdb_lookup'
}

NAMESPACE_NAME = 'newznab'
NAMESPACE_URL = 'http://www.newznab.com/DTD/2010/feeds/attributes/'
NAMESPACE_TAGNAME = 'attr'
ENCLOSURE_TYPE = 'application/x-nzb'


# list utils
def list_insert_unique(in_list, idx, element, caseinsensitive=False):
    if not isinstance(in_list, list) or element is None:
        return
    if isinstance(element, str):
        if element.isspace() or element in in_list:
            return
        elif caseinsensitive is True and element.lower() in in_list:
            return
    elif element in in_list:
        return
    in_list.insert(idx, element)


def list_append_unique(in_list, element, caseinsensitive=False):
    list_insert_unique(in_list, len(in_list), element, caseinsensitive=caseinsensitive)


def list_combine_unique(list_dst, list_source, caseinsensitive=False):
    if not isinstance(list_dst, list) or not isinstance(list_source, list):
        log.error('Cant combine lists, src/dst is not a listtype: %s, %s', list_dst, list_source)
    for item in list_source:
        list_append_unique(list_dst, item, caseinsensitive=caseinsensitive)


def _debug_dump_entry(entry):
    log.verbose('#####################################################################################')
    for key in entry:
        log.verbose('%-9s [%-30s] = %s', type(entry[key]).__name__, key, entry[key])


class Newznab(object):
    """
    Newznab search plugin
    Provide the 'api_server_url' + 'api_key' and one or more search categories via 'category'
    Most common categories are: 'tv', 'movie', 'tv/hd', 'movie/hd'
    Valid meta names for 'use_metadata': 'tvdb', 'trakt', 'tvmaze', imdb', 'tmdb'
    TIP: Use nzbhydra to perform searches on multiple indexers with one config https://github.com/theotherp/nzbhydra

    NOTE: will populate those newznab fields if available:
    'newznab_age'                   - age in days of this release
    'newznab_pubdate'               - date the indexer added the nzb to its database (aka age)
    'newznab_guid'                  - unique guid of this release
    'newznab_grabs'                 - number of grabs
    'newznab_size'                  - size in bytes of the release
    'newznab_files'                 - number of files this release (archive) has
    'newznab_usenetdate'            - date the release was posted on usenet
    'newznab_password'              - if the release uses a password ('0' no, '1' rar pass, '2' contains inner archive)
    'newznab_usenet_group'          - the usenet group patch this was posted
    'newznab_tvairdate'             - the airdate reported by the indexer
    'newznab_season'                - the season reported by the indexer
    'newznab_episode'               - the episode reported by the indexer
    'newznab_hydra_indexer_name'    - the name set in nzbhydra
    'newznab_hydra_indexer_host'    - the host url used by nzbhydra
    'newznab_hydra_indexer_score'   - the priority score set by nzbhydra config for this indexer

    Config example:
    # search by name: search in the 'tv' category, using existing names for the type ('title'...)
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        category: tv

    # search by name + age: search in the 'tv' category, using existing names for the type ('title'...)
    # maxage: auto will try to calculate the maximum possible age for the release and use it to confine the search
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        category: tv
        maxage: auto

    # meta id based: try using existing metaid's (tvdb/ragetv/imdb) to search only in the tv/hd,uhd categories
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        category:
            - tv/hd
            - tv/uhd
        use_metadata: yes

    # meta id based: try using metaid's (tvdb/ragetv/imdb) and if needed do a trakt/imdb lookup,
                     only in the movie/uhd category for releases that are not older than 1 week
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        category: movie/uhd
        use_metadata:
            - trakt
            - imdb
        maxage: 1 week

    # custom search string: builds the search string and searches in the tv/hd and a custom 5999 category
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        custom_query: "{{trakt_series_name}} {{series_id}}"
        category:
            - tv/hd
            - 5999

    # combined (meta id + custom search string): try using metaid's (tvdb/ragetv/imdb) and if needed does a tvdb lookup,
                                                also builds/uses the custom search string.
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        custom_query: "{{trakt_series_name}} {{series_id}}"
        category: tv
        use_metadata: tvdb

    # forces quotes around the search query, some ill behaving indexers wont correctly handle multiterm queries like: 'title s01e01'
    # If you notice you get results of titles that are not in the search query or wrong season/episodes, try this.
    # NOTE: will most likely break well behaving indexers, so use in a separate task/entry or use nzbhydra
    newznab:
        api_server_url: https://api.nzbindexer.com
        category: tv
        force_quotes: yes
    """

    schema = {
        'type': 'object',
        'properties': {
            'api_server_url': {'type': 'string', 'format': 'url'},
            'api_key': {'type': 'string'},
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]}, unique_items=True),
            'custom_query': {'type': 'string'},
            'force_quotes': {'type': 'boolean', 'default': False},
            'maxage': {
                'oneOf': [
                    {'type': 'string', 'format': 'interval'},
                    {'type': 'string', 'enum': ['auto']}
                ]
            },
            'use_metadata': {
                'oneOf': [
                    {'type': 'boolean'},
                    one_or_more({'type': 'string', 'enum': list(PLUGIN_LOOKUP_MAP)}, unique_items=True)
                ]
            },
        },
        'required': ['api_server_url', 'category'],
        'additionalProperties': False
    }

    def prepare_config(self, config):
        if 'use_metadata' in config:
            if 'plugins_list' not in config:
                if isinstance(config['use_metadata'], str):
                    config['use_metadata'] = [config['use_metadata']]
                if isinstance(config['use_metadata'], list):
                    plugins = []
                    for name in config['use_metadata']:
                        plugins.append(PLUGIN_LOOKUP_MAP[name])
                        config['plugins_list'] = plugins
        if 'category' in config:
            if 'category_string' not in config:
                if not isinstance(config['category'], list):
                    config['category'] = [config['category']]
                categories = config['category']
                # Convert named categories to its respective categories id number
                categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
                if len(categories) > 0:
                    config['category_string'] = ','.join(str(c) for c in categories)
        return config

    def _is_tv_entry(self, entry):
        if any(entry.get(field) for field in ['series_name', 'tvdb_id', 'tvrage_id', 'tvmaze_series_id', 'trakt_id']):
            return True
        elif any(entry.get(field) for field in ['movie_name', 'tmdb_id', 'imdb_id', 'trakt_movie_id']):
            return False
        else:
            return None

    def _has_meta_id(self, entry):
        return any(entry.get(field) for field in ['tvdb_id', 'tvrage_id', 'tvmaze_series_id', 'tmdb_id', 'imdb_id',
                                                  'trakt_movie_id', 'trakt_id'])

    def _has_supported_meta_id(self, entry):
        if self._is_tv_entry(entry) is True:
            return any(entry.get(field) for field in ['tvdb_id', 'tvrage_id'])
        elif self._is_tv_entry(entry) is False:
            return any(entry.get(field) for field in ['imdb_id'])
        else:
            return False

    def update_metadata(self, entry, config):
        if 'plugins_list' not in config:
            return entry

        show_lookup = self._is_tv_entry(entry)
        if show_lookup is None:
            log.warning('Could not determine entry type (tv/movie) for meta lookup: %s', entry)
            return entry

        search_list = []
        if show_lookup is True:
            if entry.get('series_name'):
                title, year = split_title_year(entry['series_name'])
                if year:
                    search_list.insert(0, '%s (%s)' % (title, year))
                list_append_unique(search_list, title, caseinsensitive=True)
        elif show_lookup is False:
            search_list.insert(0, entry['title'])
            if entry.get('movie_name'):
                title, year = split_title_year(entry['movie_name'])
                if year:
                    list_append_unique(search_list, '%s (%s)' % (title, year), caseinsensitive=True)
                list_append_unique(search_list, title, caseinsensitive=True)
                if entry.get('search_strings'):
                    list_combine_unique(search_list, entry('search_strings'), caseinsensitive=True)

        search_entry = Entry(entry)
        for search_string in search_list:
            search_string = search_string.strip()
            if not search_string:
                continue
            search_entry['title'] = search_string
            # update entry metadata
            if show_lookup is True:
                search_entry['series_name'] = search_string
                for plugin_name in config['plugins_list']:
                    if plugin_name == 'trakt_lookup':
                        plugin.get_plugin_by_name(plugin_name).instance.lazy_series_lookup(search_entry)
                        log.verbose('Doing `%s` for series: %s', plugin_name, search_string)
                    elif plugin_name == 'tvmaze_lookup':
                        plugin.get_plugin_by_name(plugin_name).instance.lazy_series_lookup(search_entry)
                        log.verbose('Doing `%s` for series: %s', plugin_name, search_string)
                    elif plugin_name == 'thetvdb_lookup':
                        # TODO @Andy: do we need language support?
                        plugin.get_plugin_by_name(plugin_name).instance.lazy_series_lookup(search_entry, 'en')
                        log.verbose('Doing `%s` for series: %s', plugin_name, search_string)
            elif show_lookup is False:
                for plugin_name in config['plugins_list']:
                    if plugin_name == 'trakt_lookup':
                        plugin.get_plugin_by_name('trakt_lookup').instance.lazy_movie_lookup(search_entry)
                        log.verbose('Doing `%s` for movie: %s', plugin_name, search_string)
                    elif plugin_name == 'tmdb_lookup':
                        plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(search_entry)
                        log.verbose('Doing `%s` for movie: %s', plugin_name, search_string)
                    elif plugin_name == 'imdb_lookup':
                        plugin.get_plugin_by_name('imdb_lookup').instance.lookup(search_entry)
                        log.verbose('Doing `%s` for movie: %s', plugin_name, search_string)
            if self._has_meta_id(search_entry) is not None:
                search_entry['title'] = entry['title']  # keep org. title
                return search_entry
        return entry

    def _build_base_url(self, entry, config):
        # TODO @Andy: do 't=caps' check (many indexers wont correctly handle this, nzbhydra uses 'brute force' since 0.2.169)
        if not config.get('api_server_url'):
            raise plugin.PluginError('Invalid url in config: %s', config)

        api_url = config['api_server_url'] + '/api?' + '&extended=1'
        if config.get('api_key'):
            api_url += '&apikey=%s' % config['api_key']
        if config.get('category_string'):
            api_url += '&cat=%s' % config['category_string']
        if 'maxage' in config:
            maxage = None
            if config['maxage'] == 'auto':
                estimator = plugin.get_plugin_by_name('estimate_release').instance
                est_date = estimator.estimate(entry)
                if est_date:
                    if isinstance(est_date, date):
                        est_date = datetime.combine(est_date, time())
                    est_date = est_date - timedelta(hours=12)  # add a delta to compensate TZ
                    maxage = datetime.now() - est_date
            else:
                try:
                    maxage = parse_timedelta(config['maxage'])
                except ValueError as ex:
                    log.error('Invalid maxage given in config or estimator: %s', ex)

            if maxage is not None:
                maxage = max(maxage, timedelta(days=1))  # cap to one day
                api_url += '&maxage=%s' % maxage.days
        return api_url

    def parse_from_xml(self, xml_entries):
        entries = []
        for xml_entry in xml_entries:
            new_entry = Entry()
            # skip if we have no link/title
            if not xml_entry.title or not xml_entry.link:
                continue
            # copy xml data to entry
            new_entry.update_using_map(field_map, xml_entry, ignore_none=True)
            if not all(key in new_entry for key in field_validation_list):
                log.warning('Skipping, invalid entry: %s', xml_entry.title)
                continue

            # fill extra, special data
            if xml_entry.enclosures:
                for link in xml_entry.enclosures:
                    if link.length and link.type == ENCLOSURE_TYPE:
                        new_entry['content_size'] = int(int(link.length) / 1024 / 1024)  # MB
            if 'content_size' not in new_entry or new_entry['content_size'] == 0:
                log.warning('Could not get valid filesize for entry: %s', xml_entry.title)
            if new_entry.get('newznab_pubdate'):
                new_entry['newznab_age'] = datetime.now() - new_entry['newznab_pubdate']

            entries.append(new_entry)
            #_debug_dump_entry(new_entry)  # debug
        return entries

    # feedparser cant handle namespace attributes with same tagname, so rename those nodes.
    def _make_feedparser_friendly(self, data):
        dom = minidom.parseString(data)
        items_ns = dom.getElementsByTagNameNS(NAMESPACE_URL, NAMESPACE_TAGNAME)
        if items_ns:
            for node in items_ns:
                if node.attributes and 'name' in node.attributes and 'value' in node.attributes:
                    node.tagName = NAMESPACE_NAME + ':%s' % node.attributes['name'].value
                    node.name = node.attributes['name'].value
                    node.value = node.attributes['value'].value
        return dom.toxml()

    def fill_entries_for_url(self, url, task):
        log.verbose('Fetching %s', url)
        try:
            r = task.requests.get(url + '&o=xml', timeout=20)
        except RequestException as ex:
            raise plugin.PluginError("Failed fetching url: %s error: %s" % (url, ex))

        if r and r.status_code != 200:
            raise plugin.PluginError('Unable to reach indexer url: %s' % url)

        xml_data = r.content
        try:
            xml_data = self._make_feedparser_friendly(xml_data)
        except Exception as ex:
            log.debug('Could not apply feedparser fix, trying without. Error: %s', ex)

        try:
            parsed_xml = feedparser.parse(xml_data)
        except Exception as ex:
            raise plugin.PluginError('Unable to parse XML from url: %s error: %s' % (url, ex))

        if 'error' in parsed_xml.feed:
            feed = parsed_xml.feed
            if 'code' in feed['error']:
                if 'description' in feed['error']:
                    log.error('Error code: %s detail: %s', feed['error']['code'], feed['error']['description'])
                else:
                    log.error('Error code: %s', feed['error']['code'])
            raise plugin.PluginError('Parsed XML is a error return for url: %s' % url)

        if not parsed_xml.entries:
            log.info('No entries returned from xml.')
            return []

        entries = self.parse_from_xml(parsed_xml.entries)
        if not entries:
            log.verbose('No entries parsed from xml.')

        return entries

    def _build_query_url_fragment(self, query_string, config):
        query_string = query_string.strip()
        if not query_string:
            log.error('Invalid/empty query_string given: %s', query_string)
            return None
        query = normalize_unicode(query_string)
        # query = normalize_scene(query)
        query = quote_plus(query.encode('utf8'))
        if config['force_quotes'] is True:
            query = "&q=\"%s\"" % query
        else:
            query = "&q=%s" % query
        return query

    def _build_metaid_url_fragment(self, entry):
        url_param = None
        # use first valid meta id
        if self._is_tv_entry(entry) is True:
            if entry.get('tvdb_id'):
                url_param = '&tvdbid=%s' % entry['tvdb_id']
            elif entry.get('tvrage_id'):
                url_param = '&rid=%s' % entry['tvrage_id']
                # lets not use those for now, rarely supported!
                # elif self.safe_get(entry, 'tvmaze_series_id', [basestring, int]):
                #    url_param = '&tvmazeid=%s' % entry['tvmaze_series_id']
                # elif self.safe_get(entry, 'trakt_id', [basestring, int]):
                #    url_param = '&traktid=%s' % entry['trakt_id']
        elif self._is_tv_entry(entry) is False:
            if entry.get('imdb_id'):
                imdb_str = str(entry['imdb_id'])
                url_param = '&imdbid=%s' % imdb_str.replace('tt', '')
                # tmdb_id is not supported for move lookups by indexers!
        return url_param

    def _build_series_ep_season_url_fragment(self, entry):
        url_param = None
        if 'series_episode' in entry:
            url_param = '&ep=%s' % entry['series_episode']
            # TODO @Andy: test if indexer support episode only search!
            if 'series_season' in entry:
                url_param += '&season=%s' % entry['series_season']
        return url_param

    def _get_custom_query_string(self, entry, task, config):
        if config.get('custom_query'):
            try:
                render_string = entry.render(config['custom_query'])
                render_string = render_string.strip()
                if render_string:
                    return render_string
            except RenderError as ex:
                log.error('Could not render custom_query string for: %s error: %s', entry['title'], ex)
        return None

    # API search entry
    def search(self, task, entry, config):
        config = self.prepare_config(config)

        # first check for custom_query
        custom_query_string = None
        if config.get('custom_query'):
            custom_query_string = self._get_custom_query_string(entry, task, config)
            if not custom_query_string:
                entry = self.update_metadata(entry, config)  # update metadata and try again
                custom_query_string = self._get_custom_query_string(entry, task, config)
                if not custom_query_string:
                    log.error('Could not build custom_query string for: %s ', entry['title'])
                    return []  # no fallback logic!

        meta_url = None
        ep_url = None
        # build metadata url fragments
        if 'use_metadata' in config:
            meta_url = self._build_metaid_url_fragment(entry)
            if meta_url is None:
                entry = self.update_metadata(entry, config)
                meta_url = self._build_metaid_url_fragment(entry)  # try again
            if self._is_tv_entry(entry) is True:
                ep_url = self._build_series_ep_season_url_fragment(entry)

        query_list = []
        # build meta and ep fragment
        url = self._build_base_url(entry, config)
        if meta_url and self._is_tv_entry(entry) is True and ep_url:
            url += '&t=tvsearch' + meta_url + ep_url
        elif meta_url and self._is_tv_entry(entry) is False:
            url += '&t=movie' + meta_url
        else:
            url += '&t=search'
            # use existing search_strings
            query_list = entry.get('search_strings', default=[entry['title']])
            list_append_unique(query_list, entry['title'], caseinsensitive=True)  # we trust external list?

        # use custom query in all cases (not 100% well defined behaviour in metaid cases)
        list_insert_unique(query_list, 0, custom_query_string, caseinsensitive=True)
        # do search without list
        if not query_list:
            return self.fill_entries_for_url(url, task)
        else:
            results_set = set()
            if len(query_list) > 5:  # sanity check (no we don't trust external inputs)
                log.warning('Flood protection, query_list capped to 5 entries, was: %s', len(query_list))
            for query_string in query_list[:5]:
                query_url = self._build_query_url_fragment(query_string, config)
                if query_url:
                    results = self.fill_entries_for_url(url + query_url, task)
                    if results:
                        results_set.update(results)
            return list(results_set)


@event('plugin.register')
def register_plugin():
    plugin.register(Newznab, 'newznab', api_ver=2, groups=['search'])
