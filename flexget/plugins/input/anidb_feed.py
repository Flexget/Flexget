from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
import feedparser
from xml.dom import minidom

from requests import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.qualities import Quality
from flexget.utils.tools import str_to_int, value_to_naive_utc, str_to_naive_utc, find_value, regex_search
from flexget.utils.cached_input import cached
from flexget.utils.requests import TimedLimiter


log = logging.getLogger('anidb_feed')

HEADER = {'User-agent': 'Mozilla/5.0'}  # anidb needs valid header or we get '403 Client Error'
LIMITER = TimedLimiter('anidb.net', '2 seconds')  # default anidb api limit


NAMESPACE_NAME = 'xhtml'
NAMESPACE_URL = 'http://www.w3.org/1999/xhtml'
NAMESPACE_TAGNAME = 'dl'


field_map = {
    'title': 'title',
    'url': 'link',
    'anidb_name':  # "title - 6 - episode name - [group_tag]... or (344.18 MB)"
        lambda xml: find_value('title', xml, regex=r'^(.*?) -'),
    'anidb_fid':  # http://anidb.net/f1871677
        lambda xml: str_to_int(find_value('link', xml, default='', regex=r'/f([0-9]{1,10})$')),
    'rss_pubdate':
        lambda xml: value_to_naive_utc(find_value(['updated_parsed', 'updated'], xml)),
    'anidb_feed_added':
        lambda xml: str_to_naive_utc(xml['xhtml_added']['value']),
    'anidb_feed_source': 'xhtml_source.value',
    'anidb_feed_resolution': 'xhtml_resolution.value',
    'anidb_feed_crc_status': 'xhtml_crc_status.value',
    'anidb_file_crc32':  # 'Matches official CRC (9833055b)'
        lambda xml: find_value('xhtml_crc_status.value', xml, regex=r'Matches official CRC \((([0-9]|[A-Fa-f]){8,8})\)'),
    'anidb_feed_language': 'xhtml_language.value',
    'anidb_feed_group': 'xhtml_group.value',
    'anidb_feed_group_tag':  # "HorribleSubs (HorribleSubs)"
        lambda xml: find_value('xhtml_group.value', xml, regex=r'\((.*?)\)$'),
    'anidb_feed_subtitle_language': 'xhtml_subtitle_language.value',
    'anidb_feed_priority': 'xhtml_priority.value',
    'anidb_feed_quality': 'xhtml_quality.value',
    'anidb_feed_size':  # 344.18 MB (360.895.922)
        lambda xml: str_to_int(find_value('xhtml_size.value', xml, default='', regex=r'\((([0-9]{1,3}\.|[0-9]{1,3}){1,5})\)'))
}

field_validation_list = [
    'title',
    'url',
    'anidb_name',
    'anidb_fid',
    'anidb_feed_source',
    'anidb_feed_resolution',
    'anidb_feed_group_tag',
    'anidb_feed_size'
]

# FIXME: not 100% if this is correct or move directly to qualities.py?
ANIDB_SOURCES_MAP = {
    'camcorder': 'cam',
    'TV': 'tvrip',
    'DTV': 'sdtv',
    'HDTV': 'hdtv',
    'VHS': 'tvrip',
    'VCD': 'tvrip',
    'SVCD': 'sdtv',
    'LD': 'sdtv',
    'DVD': 'dvdrip',
    'HKDVD': 'dvdrip',
    'HD-DVD': 'dvdrip',
    'Blu-ray': 'bluray',
    'www': 'webdl'
}

ANIDB_EXTRA_TYPES = [
    'special',
    'op-ending',
    'trailer-promo'
]


def _debug_dump_entry(entry):
    log.verbose('#####################################################################################')
    for key in entry:
        log.verbose('%-8s [%-30s] = %s', type(entry[key]).__name__, key, entry[key])


class AnidbFeed(object):
    """ Creates an entry for each movie or series in the AniDB file notification feeds.
        Your personalized notification feed url is shown under [Account/Settings/Notifications/link to your personal atom feed]
        See: https://wiki.anidb.net/w/Notifications
        The general main anidb file feed can also be used url: http://anidb.net/feeds/files.atom
        The feeds update every 15 minutes, which is the cache time we also use in Flexget.

        Example:
            anidb_feed:
                url: http://anidb.net/perl-bin/animedbfeed.pl?id=xxxxx................
                valid_only: yes

            valid_only: yes
            # If enabled only 'valid' entries are returned, that have a size, release group, resolution and source field
            # This happens after the file was added to anidb and has passed some initial tests/parsing

            priority: (all, medium-high, high)
            # defaults to 'all', which are the anidb notification priorities

            include: ('special', 'op-ending', 'trailer-promo')
            # Also report none regular feed file types, by default any none regular file is skipped.
            anidb_feed:
                url: http://anidb.net/perl-bin/animedbfeed.pl?id=xxxxx................
                include: special

        Adds those extra Entry fields if found:
        'content_size'
        'rss_pubdate'
        'anidb_fid'             # anidb file_id
        'anidb_file_version'    # fileversion aka v1-5
        'anidb_file_crc32'      # the anidb validated hash for this file relese
        'anidb_feed_added'
        'anidb_feed_source'
        'anidb_feed_resolution'
        'anidb_feed_crc_status'
        'anidb_feed_language'
        'anidb_feed_group'
        'anidb_feed_grouptag'
        'anidb_feed_subtitle_language'
        'anidb_feed_priority'
        'anidb_feed_quality'
        'anidb_feed_size'
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'anyOf': [{'format': 'url'}, {'format': 'file'}]},
            'priority': {'type': 'string', 'enum': ['all', 'medium-high', 'high'], 'default': 'all'},
            'valid_only': {'type': 'boolean', 'default': False},
            'include': one_or_more({'type': 'string', 'enum': ANIDB_EXTRA_TYPES}, unique_items=True)
        },
        'additionalProperties': False,
        'required': ['url'],
    }

    def prepare_config(self, config):
        if 'include' in config and not isinstance(config['include'], list):
            config['include'] = [config['include']]
        return config

    # anidb notification update interval is 15 minutes
    @cached('anidb_feed', persist='15 minutes')
    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        task.requests.add_domain_limiter(LIMITER)
        # Create entries by parsing AniDB feed
        log.verbose('Retrieving AniDB feed')
        url = re.sub(r'&pri=[1-9]', '', config['url'])  # strip existing priority
        priority_fragment = ''
        if 'animedbfeed' in url:
            priority = 0
            if config['priority'] == 'medium-high':
                priority = 1
            elif config['priority'] == 'high':
                priority = 2
            priority_fragment = '&pri=%s' % priority
        return self.fill_entries_for_url(url + priority_fragment, task, config)

    @staticmethod
    def _parse_episode_data(value):
        ep_nr = regex_search(value, r'^.*? - ([0-9]{1,3})(v([1-5]))? -')
        file_version = regex_search(value, r'^.*? - T|S|C|ED|OP|[0-9]{1,3}[a-f]?v([1-5]) -')
        is_special = regex_search(value, r'^.*? - (S[0-9]{1,3})(v([1-5]))? -')
        is_op_ed = regex_search(value, r'^.*? - ((C|OP|ED)[0-9]{1,2}[a-f]?) -')
        is_trailer = regex_search(value, r'^.*? - (T[0-9]{1,2}) -')
        if ep_nr:
            try:
                # anidb always uses absolute ep numbering, even movies get "- 1 -" !!
                ep_nr = int(ep_nr)
            except ValueError as ex:
                ep_nr = None
                log.warning('Expecting a episode nr as integer in: %s, error: %s', value, ex)
        if file_version:
            try:
                file_version = int(file_version)
            except ValueError as ex:
                file_version = None
                log.warning('Expecting a file version nr as integer in: %s, error: %s', value, ex)
        out_list = dict()
        out_list['extra'] = True
        if ep_nr is not None:
            out_list['ep'] = ep_nr
            out_list['extra'] = False
        if file_version:
            out_list['version'] = file_version
        if is_special:
            out_list['special'] = is_special
        if is_op_ed:
            out_list['op-ending'] = is_op_ed
        if is_trailer:
            out_list['trailer-promo'] = is_trailer
        return out_list

    def parse_from_xml(self, xml_entries, config):
        entries = []
        for xml_entry in xml_entries:
            new_entry = Entry()
            # skip if we have no link/title
            if not xml_entry.title or not xml_entry.link:
                continue
            # copy xml data to entry
            new_entry.update_using_map(field_map, xml_entry, ignore_none=True,
                                       ignore_values=['Raw/Unknown', 'N/A', 'Unchecked'])
            # skip entry if we cant validate
            if config['valid_only'] is True:
                if not all(key in new_entry for key in field_validation_list):
                    continue
            # skip if extra and not wanted
            episode_data = self._parse_episode_data(new_entry['title'])
            if episode_data['extra'] is True:
                if 'include' in config:
                    if not any(key in episode_data for key in config['include']):
                        continue  # is extra file
                else:
                    continue

            # some extra fixups
            new_entry['content_size'] = int(new_entry['anidb_feed_size'] / 1024 / 1024)  # MB
            # build the new 'title' mimic general scene naming convention
            anidb_name = new_entry['anidb_name']
            title_new = anidb_name
            # "title - 1 - ... - Complete Movie"
            is_movie = regex_search(new_entry['title'], r'- .*?(Complete Movie)$')
            if is_movie is not None:
                new_entry['movie_name'] = anidb_name  # FIXME: 'Complete Movie' is not guaranteed?
            else:
                new_entry['series_name'] = anidb_name
            if 'ep' in episode_data:
                if is_movie and episode_data['ep'] == 1:
                    log.debug('Hiding episode 1 numbering for Anime/Movie: %s', anidb_name)
                else:
                    new_entry['series_episode'] = episode_data['ep']  # FIXME: Does flexget support Movie episodes?
                    title_new += ' %s' % episode_data['ep']  # FIXME: is there a valid way to encode anime episodes?
                    new_entry['series_id'] = '%02d' % episode_data['ep']  # Is this valid aka a single Integer?
                    if episode_data['ep'] > 99:
                        new_entry['series_id'] = '%03d' % episode_data['ep']
            elif episode_data['extra'] is True:
                extra_string = episode_data.get('special', '')
                extra_string += episode_data.get('op-ending', '')
                extra_string += episode_data.get('trailer-promo', '')
                title_new += ' %s' % extra_string
                new_entry['series_id'] = extra_string  # FIXME: is this the correct field for extras?
            if episode_data.get('version'):
                title_new += ' v%s' % episode_data['version']  # Anidb uses 'title 9v2' indexer may use 'title 9 v2'
                new_entry['anidb_file_version'] = episode_data['version']  # TODO: Is there a official field?
            if new_entry.get('anidb_feed_group_tag'):
                title_new += ' [%s]' % new_entry['anidb_feed_group_tag']  # TODO: do we always add group?

            quality_string = ''
            # 1920x1080, 848x480, 1280x720
            if new_entry.get('anidb_feed_resolution'):
                resolution_string = regex_search(new_entry['anidb_feed_resolution'], r'x([0-9]{3,4})$')
                if resolution_string:
                    quality_string += resolution_string
            if new_entry.get('anidb_feed_source'):
                source_string = ANIDB_SOURCES_MAP.get(new_entry['anidb_feed_source'])
                if source_string:
                    quality_string += ' ' + source_string
            quality_string = quality_string.strip()
            if quality_string:
                quality = Quality(quality_string)
                new_entry['quality'] = quality
                if quality.resolution and quality.resolution.name != 'unknown':
                    title_new += ' [%s]' % quality.resolution

            new_entry['title'] = title_new
            entries.append(new_entry)
            #_debug_dump_entry(new_entry)  # debug
        return entries

    def fill_entries_for_url(self, url, task, config):
        log.verbose('Fetching %s', url)
        try:
            r = task.requests.get(url, headers=HEADER, timeout=20)
        except RequestException as ex:
            raise plugin.PluginError('Failed fetching url: %s error: %s' % (url, ex))

        if r and r.status_code != 200:
            raise plugin.PluginError('Unable to reach anidb feed url: %s' % url)

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
            log.verbose('No entries returned from xml.')
            return []

        entries = self.parse_from_xml(parsed_xml.entries, config)
        if not entries:
            log.verbose('No entries parsed from xml.')

        return entries

    def _make_feedparser_friendly(self, data):
        dom = minidom.parseString(data)
        entries = dom.getElementsByTagName('entry')
        for entry in entries:
            items_ns = entry.getElementsByTagNameNS(NAMESPACE_URL, NAMESPACE_TAGNAME)
            if items_ns:
                for node_ns in items_ns:
                    dt_nodes = node_ns.getElementsByTagName(NAMESPACE_NAME + ':dt')
                    dd_nodes = node_ns.getElementsByTagName(NAMESPACE_NAME + ':dd')
                    if len(dt_nodes) != len(dd_nodes):
                        log.trace('unexpected nodecount')
                        continue
                    for idx, dt_node in enumerate(dt_nodes):
                        if len(dt_node.childNodes) >= 1 and len(dd_nodes[idx].childNodes) >= 1:
                            if dt_node.childNodes[0].nodeValue is not None and dd_nodes[idx].childNodes[0].nodeValue is not None:
                                dt_node.tagName = NAMESPACE_NAME + ':%s' % dt_node.childNodes[0].nodeValue.replace(' ', '_')
                                dt_node.setAttribute('name', dt_node.childNodes[0].nodeValue)
                                dt_node.setAttribute('value', dd_nodes[idx].childNodes[0].nodeValue)
                                dt_node.removeChild(dt_node.childNodes[0])
                                node_ns.removeChild(dd_nodes[idx])
                                entry.appendChild(dt_node)
        return dom.toxml()


@event('plugin.register')
def register_plugin():
    plugin.register(AnidbFeed, 'anidb_feed', api_ver=2)
