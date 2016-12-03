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
from flexget.utils.tools import parse_timedelta
from flexget.utils.template import render_from_entry, RenderError
from flexget.utils.search import normalize_unicode
from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt

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

NAMESPACE_ATTRIBUTE_MAP = {
    'grabs': int,
    'size': int,
    'files': int,
    'usenetdate': datetime,
    'password': bool,
    'guid': basestring
}

NAMESPACE_NAME = 'newznab'
NAMESPACE_URL = 'http://www.newznab.com/DTD/2010/feeds/attributes/'
NAMESPACE_TAGNAME = 'attr'
NAMESPACE_PREFIX = 'newznab_'
ENCLOSURE_TYPE = 'application/x-nzb'


class Newznab(object):
    """
    Newznab search plugin
    Provide the 'api_server_url' + 'api_key and a 'search_type' and optionally newznab categories
    'search_type' is any of: 'generic', 'movie', 'tv' can be combined with category
    NOTE: If needed will do a metadata lookup for the search_types tv/movie
    TIP: Use nzbhydra to perform searches on multiple indexers with one config https://github.com/theotherp/nzbhydra

    NOTE: will populate those newznab fields if available:
    'newznab_age'       - age in days of this release
    'newznab_pubdate'   - date the indexer added the nzb to its database (aka age)
    'newznab_guid'      - unique guid of this release
    'newznab_grabs'     - number of grabs
    'newznab_size'      - size in bytes of the release
    'newznab_files'     - number of files this release (archive) has
    'newznab_usenetdate'- date the release was posted on usenet
    'newznab_password'  - if the release uses a password

    Config example:
    # simple: uses the 'title' to search in the 'tv' category
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        search_type: generic
        category: tv

    # meta id based: uses the (tvdb/ragetv id) to search only in the tv/hd,uhd categories, for results that are up-to 3 days old
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        search_type: tv
        category:
            - tv/hd
            - tv/uhd
        maxage: 3 days

    # meta id based: uses the (imdb id) to search only in the movie/uhd category, for results that are up-to 1 week old
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        search_type: movie
        category: movie/uhd
        maxage: 1 week

    # custom search string: builds the search string and searches in the tv/hd and a custom 5999 category
    newznab:
        api_server_url: https://api.nzbindexer.com
        api_key: my_apikey
        search_type:
            custom_query: "{{trakt_series_name}} {{series_id}}"
        category:
            - tv/hd
            - 5999

    # forces quotes around the search query, some ill behaving indexers wont correctly handle multiterm queries like: 'title s01e01'
    # If you notice you get results of titles that are not in the search query or wrong season/episodes, try this.
    # NOTE: will most likely break well behaving indexers, so use in a separate task/entry or use nzbhydra
    newznab:
        api_server_url: https://api.nzbindexer.com
        search_type: generic
        category: tv
        force_quotes: yes
    """

    schema = {
        'type': 'object',
        'properties': {
            'api_server_url': {'type': 'string', 'format': 'url'},
            'api_key': {'type': 'string'},
            'search_type': {
                'oneOf': [
                    {'type': 'string', 'enum': ['generic', 'tv', 'movie']},
                    {
                        'type': 'object',
                        'properties': {
                            'custom_query': {'type': 'string'},
                        },
                        'required': ['custom_query']
                    },
                ],
            },
            'category': one_or_more({
                'oneOf': [
                    {'type': 'integer'},
                    {'type': 'string', 'enum': list(CATEGORIES)},
                ]}, unique_items=True),
            'maxage': {'type': 'string', 'format': 'interval'},
            'force_quotes': {'type': 'boolean', 'default': False},
        },
        'required': ['api_server_url', 'search_type'],
        'additionalProperties': False
    }

    @staticmethod
    def safe_get(in_object, keynames, types=basestring, default=None, lazy=True):
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
            # TODO @Andy: double check int case for {'key': 0} -> get() is None
            found = in_object.get(key)
            if not found and lazy:
                found = in_object.get(key.lower())
            for thetype in types:
                if found and isinstance(found, thetype):
                    if isinstance(found, basestring) and found.isspace():
                        continue
                    return found
        return default

    @staticmethod
    def convert_to_naive_utc(value):
        parsed_date = None
        try:
            parsed_date = dateutil_parse(value, fuzzy=True)
            try:
                parsed_date = parsed_date.astimezone(tz.tzutc()).replace(tzinfo=None)
            except ValueError:
                parsed_date = parsed_date.replace(tzinfo=None)
        except ValueError as ex:
            log.warning('Invalid datetime field format: %s error: %s' % (value, ex))
        except Exception as ex:
            log.trace('Unexpected datetime field: %s error: %s' % (value, ex))
        return parsed_date

    @staticmethod
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

    @staticmethod
    def string_to_bool(value):
        return value.lower() in ('yes', 'true', 't', '1', 'y')

    # @staticmethod
    # def dump_entry(entry):
    #     log.verbose('#####################################################################################')
    #     for key in entry:
    #         log.verbose('Entry: [%s] = %s' % (key, entry[key]))
    #     log.verbose('#####################################################################################')

    def update_metadata(self, task, entry, config):
        # lets guess the generic type
        do_show_lookup = False
        do_movie_lookup = False
        if self.safe_get(config, 'search_type', dict) and self.safe_get(config['search_type'], 'custom_query'):
            if self.safe_get(entry, 'series_name') or self.safe_get(entry, 'tvdb_id'):
                do_show_lookup = True
            else:
                do_movie_lookup = True  # imdb_id

        # update entry metadata based on task config
        if config['search_type'] == 'tv' or do_show_lookup:
            if self.safe_get(task.config, 'trakt_lookup', [bool, dict]):
                plugin.get_plugin_by_name('trakt_lookup').instance.lazy_series_lookup(entry)
                log.verbose('Doing trakt_lookup for: %s' % self.safe_get(entry, 'title'))
            if self.safe_get(task.config, 'tvmaze_lookup', bool):
                plugin.get_plugin_by_name('tvmaze_lookup').instance.lazy_series_lookup(entry)
                log.verbose('Doing tvmaze_lookup for: %s' % self.safe_get(entry, 'title'))
            # default fallback
            if self.safe_get(task.config, 'thetvdb_lookup', bool) or not self.safe_get(entry, 'tvdb_id', [basestring,
                                                                                                          int]):
                plugin.get_plugin_by_name('thetvdb_lookup').instance.lazy_series_lookup(entry, 'en')
                log.verbose('Doing thetvdb_lookup for: %s' % self.safe_get(entry, 'title'))
        elif config['search_type'] == 'movie' or do_movie_lookup:
            if self.safe_get(task.config, 'trakt_lookup', [bool, dict]):
                plugin.get_plugin_by_name('trakt_lookup').instance.lazy_movie_lookup(entry)
                log.verbose('Doing trakt_lookup for: %s' % self.safe_get(entry, 'title'))
            if self.safe_get(task.config, 'tmdb_lookup', bool):
                plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
                log.verbose('Doing tmdb_lookup for: %s' % self.safe_get(entry, 'title'))
            # default fallback
            if self.safe_get(task.config, 'imdb_lookup', bool) or not self.safe_get(entry, 'imdb_id', [basestring,
                                                                                                       int]):
                plugin.get_plugin_by_name('imdb_lookup').instance.lookup(entry)
                log.verbose('Doing imdb_lookup for: %s' % self.safe_get(entry, 'title'))
                # TODO @Andy: more robust fallback logic (clean title from dates ....)

    def get_metaid_url_parameter(self, task, entry, config):
        # only use for tv/movie search type
        if config['search_type'] != 'tv' and config['search_type'] != 'movie':
            return ''

        self.update_metadata(task, entry, config)

        url_param = ''
        # use first valid meta id
        if self.safe_get(config, 'search_type') == 'tv':
            if self.safe_get(entry, 'tvdb_id', [basestring, int]):
                url_param = '&tvdbid=%s' % self.safe_get(entry, 'tvdb_id', [basestring, int])
            elif self.safe_get(entry, 'tvrage_id', [basestring, int]):
                url_param = '&rid=%s' % self.safe_get(entry, 'tvrage_id', [basestring, int])
            # lets not use those for now, rarely supported!
            # elif self.safe_get(entry, 'tvmaze_series_id', [basestring, int]):
            #    url_param = '&tvmazeid=%s' % self.safe_get(entry, 'tvmaze_series_id', [basestring, int])
            # elif self.safe_get(entry, 'trakt_id', [basestring, int]):
            #    url_param = '&traktid=%s' % self.safe_get(entry, 'trakt_id', [basestring, int])
            if not url_param:
                log.error('Could not get valid meta id for series: %s' % self.safe_get(entry, ['series_name', 'title']))
        elif self.safe_get(config, 'search_type') == 'movie':
            if self.safe_get(entry, 'imdb_id', [basestring, int]):
                imdb_str = str(self.safe_get(entry, 'imdb_id', [basestring, int]))
                url_param = '&imdbid=%s' % imdb_str.replace('tt', '')
                # tmdb is not supported for move lookups by indexers!
            if not url_param:
                log.error('Could not get imdb_id for movie: %s' % self.safe_get(entry, ['movie_name', 'title']))

        return url_param

    def build_base_url(self, config):
        log.debug(type(config))

        # TODO @Andy: do 't=caps' check (many indexers wont correctly handle this, nzbhydra uses 'brute force' since 0.2.169)

        if not self.safe_get(config, 'api_server_url'):
            raise plugin.PluginError('Invalid url: %s' % self.safe_get(config, 'api_server_url'))

        api_url = config['api_server_url'] + '/api?' + '&extended=1'

        if self.safe_get(config, 'api_key'):
            api_url += '&apikey=%s' % self.safe_get(config, 'api_key')

        if config['search_type'] == 'tv':
            api_url += '&t=tvsearch'
        elif config['search_type'] == 'movie':
            api_url += '&t=movie'
        else:
            api_url += '&t=search'

        if self.safe_get(config, 'category', [basestring, list]):
            categories = self.safe_get(config, 'category', [basestring, list])
            if categories and not isinstance(categories, list):
                categories = [categories]
            # Convert named categories to its respective categories id number
            categories = [c if isinstance(c, int) else CATEGORIES[c] for c in categories]
            if len(categories) > 0:
                categories_string = ','.join(str(c) for c in categories)
                api_url += '&cat=%s' % categories_string
        # carefull, 0 is defined!
        if 'maxage' in config:
            api_url += '&maxage=%s' % parse_timedelta(config['maxage']).days

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
                parsed_date = self.convert_to_naive_utc(xml_entry.published)
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
        if tagname in entry and entry.get(tagname):
            value = entry.get(tagname)  # use existing, but do type check
        elif tagname in xml_entry:
            if isinstance(xml_entry[tagname], dict) and 'value' in xml_entry[tagname]:
                value = xml_entry[tagname]['value']
            elif isinstance(xml_entry[tagname], basestring):
                value = xml_entry[tagname]

        if value:
            if isinstance(value, in_type):
                entry[tagname] = value
            elif in_type == int or in_type == float:
                number = self.convert_to_number(value)
                if number:
                    entry[tagname] = number
            elif in_type == datetime:
                date = self.convert_to_naive_utc(value)
                if date:
                    entry[tagname] = date
            elif in_type == bool:
                boolvalue = None
                if isinstance(value, basestring):
                    if self.string_to_bool(value):
                        boolvalue = True
                if not boolvalue:
                    number = self.convert_to_number(value)
                    if number and number > 0:
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
            log.error("Failed fetching urk: %s error: %s" % (url, ex))
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

    def get_query_param(self, query_string, entry, task, config):
        query = query_string
        if self.safe_get(config, 'search_type', dict) and self.safe_get(config['search_type'], 'custom_query'):
            custom_query = self.safe_get(config['search_type'], 'custom_query')
            try:
                entry.task = task
                query = render_from_entry(custom_query, entry)
            except RenderError as ex:
                log.warning('Could not build custom_query string for: %s error: %s' % (entry['title'], ex))

        query = normalize_unicode(query)
        # query = normalize_scene(query)
        query = quote_plus(query.encode('utf8'))
        if config['force_quotes'] is True:
            query = "&q=\"%s\"" % query
        else:
            query = "&q=%s" % query
        return query

    # API search entry
    def search(self, task, entry, config):
        if config['search_type'] == 'movie':
            return self.do_search_movie(entry, task, config)
        elif config['search_type'] == 'tv':
            return self.do_search_tv(entry, task, config)
        else:
            return self.do_search_generic(entry, task, config)

    def do_search_generic(self, entry, task, config):
        url = self.build_base_url(config)
        self.update_metadata(task, entry, config)

        query = self.get_query_param(entry['title'], entry, task, config)
        if not query:
            log.verbose('Skipping Entry: %s, because invalid search query string found.' % entry['title'])
            return []

        url += query
        return self.fill_entries_for_url(url, task)

    def do_search_tv(self, entry, task, config):
        # normally this should be used with next_series_episodes who has provided season and episodenumber
        parsed_name = ''
        # carefull episode 0 is valid
        if 'series_episode' not in entry:
            # try to fix
            id_type = self.safe_get(entry, 'series_id_type', default='auto')
            parser = plugin.get_plugin_by_name('parsing').instance
            parsed = parser.parse_series(data=entry['title'], identified_by=id_type, allow_seasonless=allow_seasonless)
            if parsed and parsed.valid:
                parsed_name = normalize_name(remove_dirt(parsed.name))
                entry['series_episode'] = parsed.episode
                if 'series_season' not in entry:
                    if self.safe_get(entry, 'series_id_type') == 'ep':
                        entry['series_season'] = parsed.season

        if 'series_episode' not in entry:
            log.error('Could not get valid episode numbering for series lookup, skipping: %s' % entry['title'])
            return []

        # build final url
        url = self.build_base_url(config)
        url_metaid_param = self.get_metaid_url_parameter(task, entry, config)
        if url_metaid_param:
            url += url_metaid_param
        else:  # fallback to name (do we use the 'search_strings' array?)
            if self.safe_get(entry, 'series_name'):
                query_name = self.safe_get(entry, 'series_name')
            elif parsed_name:
                query_name = parsed_name
            else:
                query_name = self.safe_get(entry, 'title')
            if query_name:
                url += self.get_query_param(query_name, entry, task, config)
                log.verbose('Doing fallback search via name: %s for: %s' % (query_name, entry['title']))
            else:
                log.error('Could not get valid fallback name for: %s' % entry['title'])
                return []

        if 'series_episode' in entry:
            url += '&ep=%s' % entry['series_episode']
        if 'series_season' in entry:
            url += '&season=%s' % entry['series_season']  # TODO @Andy: test if indexer support episode only search!
        return self.fill_entries_for_url(url, task)

    def do_search_movie(self, entry, task, config):
        url = self.build_base_url(config)
        url_metaid_param = self.get_metaid_url_parameter(task, entry, config)
        if url_metaid_param:
            url += url_metaid_param
        else:  # fallback to name (do we use the 'search_strings' array?)
            # TODO @Andy: maybe do a clean (plugin_parsing) call instead of title?
            query_name = self.safe_get(entry, ['movie_name', 'title'])
            if query_name:
                url += self.get_query_param(query_name, entry, task, config)
                log.verbose('Doing fallback search via name: %s for: %s' % (query_name, entry['title']))
            else:
                log.error('Could not get valid fallback name for: %s' % entry['title'])
                return []
        return self.fill_entries_for_url(url, task)


@event('plugin.register')
def register_plugin():
    plugin.register(Newznab, 'newznab', api_ver=2, groups=['search'])
