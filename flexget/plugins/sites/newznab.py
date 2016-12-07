from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from time import mktime

from xml.dom import minidom
from past.builtins import basestring
from datetime import datetime
from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tz
from future.moves.urllib.parse import quote_plus

import re
import logging
import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.tools import parse_timedelta, str_to_boolean, split_title_year
from flexget.utils.search import normalize_unicode

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

# NOTE: all lowercase only
NAMESPACE_ATTRIBUTE_MAP = {
    'grabs': int,
    'size': int,
    'files': int,
    'usenetdate': datetime,
    'password': bool,
    'guid': basestring,
    'hydraindexername': basestring,
    'hydraindexerhost': basestring,
    'hydraindexerscore': int
}

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
NAMESPACE_PREFIX = 'newznab_'
ENCLOSURE_TYPE = 'application/x-nzb'


# utils
def list_insert_unique(in_list, idx, element, caseinsensitive=False):
    if not isinstance(in_list, list) or element is None:
        return
    if isinstance(element, basestring):
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
        log.error('Cant combine lists, src/dst is not a listtype: %s %s' % (list_dst, list_source))
    for item in list_source:
        list_append_unique(list_dst, item, caseinsensitive=caseinsensitive)


def safe_get(in_object, keynames, types=basestring, default=None, caseinsensitive=True):
    invert_op = getattr(in_object, "get", None)
    if not invert_op or not callable(invert_op):
        log.warning('Object has no get() function: %s' % in_object)
        return default

    if not isinstance(keynames, list):
        keynames = [keynames]
    if not isinstance(types, list):
        types = [types]

    for key in keynames:
        if not isinstance(key, basestring):
            log.warning('Key is not a string: %s' % key)
            continue
        found = in_object.get(key)
        if found is None and caseinsensitive is True:
            found = in_object.get(key.lower())
        for thetype in types:
            if found is not None and isinstance(found, thetype):
                if isinstance(found, basestring) and found.isspace():
                    continue
                return found
    return default


def convert_to_naive_utc(valuestring):
    parsed_date = None
    try:
        parsed_date = dateutil_parse(valuestring, fuzzy=True)
        try:
            parsed_date = parsed_date.astimezone(tz.tzutc()).replace(tzinfo=None)
        except ValueError:
            parsed_date = parsed_date.replace(tzinfo=None)
    except ValueError as ex:
        log.warning('Invalid datetime field format: %s error: %s' % (valuestring, ex))
    except Exception as ex:
        log.trace('Unexpected datetime field: %s error: %s' % (valuestring, ex))
    return parsed_date


def convert_to_number(valuestring):
    number = None
    try:
        number = int(valuestring)
    except ValueError:
        try:
            number = float(valuestring)
        except ValueError:
            log.trace('Invalid number field: %s' % valuestring)
    except Exception as ex:
        log.trace('Invalid number field: %s error: %s' % (valuestring, ex))
    return number

    # def dump_entry(entry):
    #     log.verbose('#####################################################################################')
    #     for key in entry:
    #         log.verbose('Entry: [%s] = %s' % (key, entry[key]))
    #     log.verbose('#####################################################################################')


class Newznab(object):
    """
    Newznab search plugin
    Provide the 'api_server_url' + 'api_key' and one or more search categories via 'category'
    Most common categories are: 'tv', 'movie', 'tv/hd', 'movie/hd'
    Valid meta names for 'use_metadata': 'tvdb', 'trakt', 'tvmaze', imdb', 'tmdb'
    TIP: Use nzbhydra to perform searches on multiple indexers with one config https://github.com/theotherp/nzbhydra

    NOTE: will populate those newznab fields if available:
    'newznab_age'               - age in days of this release
    'newznab_pubdate'           - date the indexer added the nzb to its database (aka age)
    'newznab_guid'              - unique guid of this release
    'newznab_grabs'             - number of grabs
    'newznab_size'              - size in bytes of the release
    'newznab_files'             - number of files this release (archive) has
    'newznab_usenetdate'        - date the release was posted on usenet
    'newznab_password'          - if the release uses a password
    'newznab_hydraindexername'  - the name set in nzbhydra
    'newznab_hydraindexerhost'  - the host url used by nzbhydra
    'newznab_hydraindexerscore' - the priority score set by nzbhydra config for this indexer

    Config example:
    # search by name: search in the 'tv' category, using existing names for the type ('title'...)
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        category: tv

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
            'maxage': {'type': 'string', 'format': 'interval'},
            'custom_query': {'type': 'string'},
            'force_quotes': {'type': 'boolean', 'default': False},
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
                if isinstance(config['use_metadata'], basestring):
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

    def is_tv_entry(self, entry):
        if safe_get(entry, ['series_name', 'tvdb_id', 'tvrage_id', 'tvmaze_series_id', 'trakt_id'],
                    [basestring, int]):
            return True
        elif safe_get(entry, ['movie_name', 'tmdb_id', 'imdb_id', 'trakt_movie_id'], [basestring, int]):
            return False
        else:
            return None

    def has_meta_id(self, entry):
        return safe_get(entry, ['tvdb_id', 'tvrage_id', 'tvmaze_series_id', 'tmdb_id', 'imdb_id',
                                'trakt_movie_id', 'trakt_id'], [basestring, int])

    def has_supported_meta_id(self, entry):
        if self.is_tv_entry(entry) is True:
            return safe_get(entry, ['tvdb_id', 'tvrage_id'], [basestring, int])
        elif self.is_tv_entry(entry) is False:
            return safe_get(entry, ['imdb_id'], [basestring, int])
        else:
            return False

    def update_metadata(self, entry, config):
        if not safe_get(config, 'plugins_list', list):
            return entry

        show_lookup = self.is_tv_entry(entry)
        if show_lookup is None:
            log.warning('Could not determine entry type (tv/movie) for meta lookup: %s' % entry)
            return entry

        search_list = []
        if show_lookup is True:
            if safe_get(entry, 'series_name'):
                title, year = split_title_year(entry['series_name'])
                if year:
                    search_list.insert(0, '%s (%s)' % (title, year))
                list_append_unique(search_list, title, caseinsensitive=True)
        elif show_lookup is False:
            search_list.insert(0, entry['title'])
            if safe_get(entry, 'movie_name'):
                title, year = split_title_year(entry['movie_name'])
                if year:
                    list_append_unique(search_list, '%s (%s)' % (title, year), caseinsensitive=True)
                list_append_unique(search_list, title, caseinsensitive=True)
                if safe_get(entry, 'search_strings', list):
                    list_combine_unique(search_list, entry('search_strings'), caseinsensitive=True)

        search_entry = Entry(entry)
        for search_string in search_list:
            if search_string is None or not isinstance(search_string, basestring) or search_string.isspace():
                continue
            search_entry['title'] = search_string
            # update entry metadata
            if show_lookup is True:
                search_entry['series_name'] = search_string
                for plugin_name in config['plugins_list']:
                    if plugin_name == 'trakt_lookup':
                        plugin.get_plugin_by_name(plugin_name).instance.lazy_series_lookup(search_entry)
                        log.verbose('Doing `%s` for series: %s' % (plugin_name, search_string))
                    elif plugin_name == 'tvmaze_lookup':
                        plugin.get_plugin_by_name(plugin_name).instance.lazy_series_lookup(search_entry)
                        log.verbose('Doing `%s` for series: %s' % (plugin_name, search_string))
                    elif plugin_name == 'thetvdb_lookup':
                        # TODO @Andy: do we need language support?
                        plugin.get_plugin_by_name(plugin_name).instance.lazy_series_lookup(search_entry, 'en')
                        log.verbose('Doing `%s` for series: %s' % (plugin_name, search_string))
            elif show_lookup is False:
                for plugin_name in config['plugins_list']:
                    if plugin_name == 'trakt_lookup':
                        plugin.get_plugin_by_name('trakt_lookup').instance.lazy_movie_lookup(search_entry)
                        log.verbose('Doing `%s` for movie: %s' % (plugin_name, search_string))
                    elif plugin_name == 'tmdb_lookup':
                        plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(search_entry)
                        log.verbose('Doing `%s` for movie: %s' % (plugin_name, search_string))
                    elif plugin_name == 'imdb_lookup':
                        plugin.get_plugin_by_name('imdb_lookup').instance.lookup(search_entry)
                        log.verbose('Doing `%s` for movie: %s' % (plugin_name, search_string))
            if self.has_meta_id(search_entry) is not None:
                search_entry['title'] = entry['title']  # keep org. title
                return search_entry
        return entry

    def build_base_url(self, config):
        # TODO @Andy: do 't=caps' check (many indexers wont correctly handle this, nzbhydra uses 'brute force' since 0.2.169)
        if not safe_get(config, 'api_server_url'):
            raise plugin.PluginError('Invalid url in config: %s' % config)

        api_url = config['api_server_url'] + '/api?' + '&extended=1'
        if safe_get(config, 'api_key'):
            api_url += '&apikey=%s' % config['api_key']
        if safe_get(config, 'category_string'):
            api_url += '&cat=%s' % config['category_string']
        # carefull, 0 is defined!
        if safe_get(config, 'maxage'):
            try:
                api_url += '&maxage=%s' % parse_timedelta(config['maxage']).days
            except Exception as ex:
                log.error('Invalid maxage given in config: %s' % ex)
        return api_url

    def parse_from_xml(self, xml_entries):
        entries = []
        for xml_entry in xml_entries:
            new_entry = Entry()
            # skip if we have no link/title
            if not xml_entry.title or not xml_entry.link:
                continue
            # fill base data
            new_entry['title'] = xml_entry.title
            new_entry['url'] = xml_entry.link
            if xml_entry.enclosures:
                for link in xml_entry.enclosures:
                    if link.length and link.type == ENCLOSURE_TYPE:
                        new_entry['content_size'] = int(int(link.length) / 1024 / 1024)  # MB
            if 'content_size' not in new_entry or new_entry['content_size'] == 0:
                log.warning('Could not get valid filesize for entry: %s' % xml_entry.title)

            # store some usefully data in the namespace
            if xml_entry.id:
                guid_splits = re.split('[/=]', xml_entry.id)
                new_entry[NAMESPACE_PREFIX + 'guid'] = guid_splits.pop()
            if xml_entry.published_parsed:
                new_entry[NAMESPACE_PREFIX + 'pubdate'] = datetime.fromtimestamp(mktime(xml_entry.published_parsed))
            elif xml_entry.published:
                parsed_date = convert_to_naive_utc(xml_entry.published)
                if parsed_date:
                    new_entry[NAMESPACE_PREFIX + 'pubdate'] = parsed_date
            if (NAMESPACE_PREFIX + 'pubdate') in new_entry:
                try:
                    tdelta = datetime.now() - new_entry[NAMESPACE_PREFIX + 'pubdate']
                    new_entry[NAMESPACE_PREFIX + 'age'] = max(0, int(tdelta.days))  # store simple age value in days
                except Exception as ex:
                    log.trace('Cant calculate Age via pubdate: %s in Entry: %s error : %s' % (
                        new_entry[NAMESPACE_PREFIX + 'pubdate'], xml_entry.title, ex))

            # add some usefully attributes to the namespace
            self.fill_namespace_attributes(xml_entry, new_entry)
            entries.append(new_entry)
            # self.dump_entry(new_entry)
        return entries

    def set_ns_attribute(self, name, xml_entry, entry, in_type=basestring):
        tagname = NAMESPACE_PREFIX + name
        value = None
        if tagname in entry and entry.get(tagname) is not None:
            value = entry.get(tagname)  # use existing, but do type check
        elif tagname in xml_entry:
            if isinstance(xml_entry[tagname], dict) and 'value' in xml_entry[tagname]:
                value = xml_entry[tagname]['value']
            elif isinstance(xml_entry[tagname], basestring):
                value = xml_entry[tagname]

        if value is not None:
            if isinstance(value, in_type):
                entry[tagname] = value
            elif in_type == int or in_type == float:
                number = convert_to_number(value)
                if number is not None:
                    entry[tagname] = number
            elif in_type == datetime:
                date = convert_to_naive_utc(value)
                if date is not None:
                    entry[tagname] = date
            elif in_type == bool:
                boolvalue = None
                if isinstance(value, basestring):
                    if str_to_boolean(value):
                        boolvalue = True
                if not boolvalue:
                    number = convert_to_number(value)
                    if number is not None and number > 0:
                        boolvalue = True
                    else:
                        boolvalue = False
                entry[tagname] = boolvalue
            else:
                log.warning('Unsupported attribute type: %s via name: %s' % (in_type, tagname))

    def fill_namespace_attributes(self, xml_entry, entry):
        for key in NAMESPACE_ATTRIBUTE_MAP:
            self.set_ns_attribute(key, xml_entry, entry, NAMESPACE_ATTRIBUTE_MAP[key])

    # feedparser cant handle namespace attributes with same tagname, so rename those nodes.
    def make_feedparser_friendly(self, data):
        try:
            dom = minidom.parseString(data)
            items_ns = dom.getElementsByTagNameNS(NAMESPACE_URL, NAMESPACE_TAGNAME)
            if items_ns:
                for node in items_ns:
                    if node.attributes and 'name' in node.attributes and 'value' in node.attributes:
                        node.tagName = NAMESPACE_NAME + ':%s' % node.attributes['name'].value
                        node.name = node.attributes['name'].value
                        node.value = node.attributes['value'].value
        except Exception as ex:
            log.trace('Unable to rename nodes in XML: %s' % ex)
            return None
        return dom.toxml()

    def fill_entries_for_url(self, url, task):
        log.verbose('Fetching %s' % url)

        try:
            r = task.requests.get(url + '&o=xml', timeout=20)
        except Exception as ex:
            log.error("Failed fetching url: %s error: %s" % (url, ex))
            return []

        if r and r.status_code != 200:
            raise plugin.PluginError('Unable to reach indexer url: %s' % url)

        fixed_xml = self.make_feedparser_friendly(r.content)
        try:
            # TODO @Andy: proper result 'offset' support ({"offset":"0","total":"100"})
            if fixed_xml:
                parsed_xml = feedparser.parse(fixed_xml)
            else:
                parsed_xml = feedparser.parse(r.content)
            xml_feed = parsed_xml.feed
            if 'error' in xml_feed:
                if 'code' in xml_feed['error']:
                    if 'description' in xml_feed['error']:
                        log.error(
                            'Error code: %s detail: %s' % (xml_feed['error']['code'], xml_feed['error']['description']))
                    else:
                        log.error('Error code: %s' % xml_feed['error']['code'])
        except Exception as ex:
            log.error('Unable to parse the XML from url: %s error: %s' % (url, ex))
            return []

        if not len(parsed_xml.entries) > 0:
            log.info('No entries returned from xml.')
            return []

        entries = self.parse_from_xml(parsed_xml.entries)
        if len(entries) == 0:
            log.verbose('No entries parsed from xml.')
        # else:
        #   self.dump_entry(entries[0])

        return entries

    def build_query_url_fragment(self, query_string, config):
        if query_string is None or not isinstance(query_string, basestring) or query_string.isspace():
            return None
        query = normalize_unicode(query_string)
        # query = normalize_scene(query)
        query = quote_plus(query.encode('utf8'))
        if config['force_quotes'] is True:
            query = "&q=\"%s\"" % query
        else:
            query = "&q=%s" % query
        return query

    def build_metaid_url_fragment(self, entry):
        url_param = None
        # use first valid meta id
        if self.is_tv_entry(entry) is True:
            if safe_get(entry, 'tvdb_id', [basestring, int]):
                url_param = '&tvdbid=%s' % entry['tvdb_id']
            elif safe_get(entry, 'tvrage_id', [basestring, int]):
                url_param = '&rid=%s' % entry['tvrage_id']
                # lets not use those for now, rarely supported!
                # elif self.safe_get(entry, 'tvmaze_series_id', [basestring, int]):
                #    url_param = '&tvmazeid=%s' % entry['tvmaze_series_id']
                # elif self.safe_get(entry, 'trakt_id', [basestring, int]):
                #    url_param = '&traktid=%s' % entry['trakt_id']
        elif self.is_tv_entry(entry) is False:
            if safe_get(entry, 'imdb_id', [basestring, int]):
                imdb_str = str(entry['imdb_id'])
                url_param = '&imdbid=%s' % imdb_str.replace('tt', '')
                # tmdb_id is not supported for move lookups by indexers!
        return url_param

    def build_series_ep_season_url_fragment(self, entry):
        url_param = None
        if safe_get(entry, 'series_episode', [basestring, int]):
            url_param = '&ep=%s' % entry['series_episode']
            # TODO @Andy: test if indexer support episode only search!
            if safe_get(entry, 'series_season', [basestring, int]):
                url_param += '&season=%s' % entry['series_season']
        return url_param

    def get_custom_query_string(self, entry, task, config):
        if safe_get(config, 'custom_query'):
            if hasattr(entry, 'task') and entry.task is None:
                entry.task = task  # FIXME: remove if fixed in master
            render_string = None
            try:
                render_string = entry.render(config['custom_query'])
            except Exception as ex:
                log.trace('Could not render custom_query string for: %s error: %s' % (entry['title'], ex))
            if render_string and not render_string.isspace():
                return render_string
        return None

    # API search entry
    def search(self, task, entry, config):
        config = self.prepare_config(config)

        # first check for custom_query
        custom_query_string = None
        if safe_get(config, 'custom_query'):
            custom_query_string = self.get_custom_query_string(entry, task, config)
            if not custom_query_string:
                entry = self.update_metadata(entry, config)  # update metadata and try again
                custom_query_string = self.get_custom_query_string(entry, task, config)
                if not custom_query_string:
                    log.error('Could not build custom_query string for: %s ' % entry['title'])
                    return []  # no fallback logic!

        meta_url = None
        ep_url = None
        # build metadata url fragments
        if 'use_metadata' in config:
            meta_url = self.build_metaid_url_fragment(entry)
            if meta_url is None:
                entry = self.update_metadata(entry, config)
                meta_url = self.build_metaid_url_fragment(entry)  # try again
            if self.is_tv_entry(entry) is True:
                ep_url = self.build_series_ep_season_url_fragment(entry)

        query_list = []
        # build meta and ep fragment
        url = self.build_base_url(config)
        if meta_url and self.is_tv_entry(entry) is True and ep_url:
            url += '&t=tvsearch' + meta_url + ep_url
        elif meta_url and self.is_tv_entry(entry) is False:
            url += '&t=movie' + meta_url
        else:
            url += '&t=search'
            # use existing search_strings
            query_list = safe_get(entry, 'search_strings', list, default=[entry['title']])

        # use custom query in all cases (not 100% well defined behaviour in metaid cases)
        list_insert_unique(query_list, 0, custom_query_string, caseinsensitive=True)
        # do search without list
        if query_list is None or len(query_list) == 0:
            return self.fill_entries_for_url(url, task)
        else:
            results_set = set()
            for query_string in query_list:
                query_url = self.build_query_url_fragment(query_string, config)
                if query_url:
                    results = self.fill_entries_for_url(url + query_url, task)
                    if len(results) > 0:
                        results_set.update(results)
            return list(results_set)


@event('plugin.register')
def register_plugin():
    plugin.register(Newznab, 'newznab', api_ver=2, groups=['search'])
