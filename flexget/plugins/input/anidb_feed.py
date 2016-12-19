from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
import feedparser
from xml.dom import minidom
from time import mktime
from datetime import datetime

from requests import RequestException

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.qualities import Quality
from flexget.utils.tools import str_to_boolean, str_to_naive_utc, str_to_number
from flexget.utils.cached_input import cached
from flexget.utils.requests import TimedLimiter


log = logging.getLogger('anidb_feed')

HEADER = {'User-agent': 'Mozilla/5.0'}  # anidb needs valid header or we get '403 Client Error'
LIMITER = TimedLimiter('anidb.net', '2 seconds')  # default anidb api limit


NAMESPACE_NAME = 'xhtml'
NAMESPACE_URL = 'http://www.w3.org/1999/xhtml'
NAMESPACE_TAGNAME = 'dl'


# NOTE: all lowercase only
field_map = {
    'anidb_feed_added': lambda xml: str_to_naive_utc(xml['xhtml_added']['value']),
    'anidb_feed_source': 'xhtml_source.value',
    'anidb_feed_resolution': 'xhtml_resolution.value',
    'anidb_feed_crc_status': 'xhtml_crc_status.value',
    'anidb_feed_language': 'xhtml_language.value',
    'anidb_feed_group': 'xhtml_group.value',
    'anidb_feed_subtitle_language': 'xhtml_subtitle_language.value',
    'anidb_feed_priority': 'xhtml_priority.value',
    'anidb_feed_quality': 'xhtml_quality.value',
    'anidb_feed_size': 'xhtml_size.value'
}

field_validation_list = [
    'anidb_feed_source',
    'anidb_feed_resolution',
    'anidb_feed_group',
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
    #@cached('anidb_feed', persist='15 minutes')
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

    def get_value_via_regex(self, key, entry, re_string, group_nr=1):
        result = None
        if entry.get(key):
            value_string = entry[key]
            if isinstance(value_string, str) and not value_string.isspace():
                match = re.search(re_string, value_string)
                if match and match.group(group_nr) and not match.group(group_nr).isspace():
                    result = match.group(group_nr)
            else:
                log.error('Expecting string for re lookup got: %s, type: %s', value_string, type(value_string))
        return result

    def parse_episode_data(self, key, entry):
        ep_nr = self.get_value_via_regex(key, entry, r'^.*? - ([0-9]{1,3})(v([1-5]))? -')
        file_version = self.get_value_via_regex(key, entry, r'^.*? - T|S|C|ED|OP|[0-9]{1,3}[a-f]?v([1-5]) -')
        is_special = self.get_value_via_regex(key, entry, r'^.*? - (S[0-9]{1,3})(v([1-5]))? -')
        is_op_ed = self.get_value_via_regex(key, entry, r'^.*? - ((C|OP|ED)[0-9]{1,2}[a-f]?) -')
        is_trailer = self.get_value_via_regex(key, entry, r'^.*? - (T[0-9]{1,2}) -')
        if ep_nr:
            try:
                # anidb always uses absolute ep numbering, even movies get "- 1 -" !!
                ep_nr = int(ep_nr)
            except ValueError as ex:
                ep_nr = None
                log.warning('Expecting a episode nr as integer in: %s, error: %s', entry[key], ex)
        if file_version:
            try:
                file_version = int(file_version)
            except ValueError as ex:
                file_version = None
                log.warning('Expecting a file version nr as integer in: %s, error: %s', entry[key], ex)
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
            # fill base data
            new_entry['title'] = xml_entry.title  # needs to-be fixed manually later
            new_entry['url'] = xml_entry.link  # file link
            episode_data = self.parse_episode_data('title', new_entry)
            if episode_data['extra'] is True:
                if 'include' in config:
                    if not any(key in episode_data for key in config['include']):
                        continue  # is extra file
                else:
                    continue
            # store some usefully data in the namespace
            fid_string = self.get_value_via_regex('url', new_entry, r'/f([0-9]{1,10})$')
            if fid_string:
                try:
                    fid = int(fid_string)
                    if fid is not None:
                        new_entry['anidb_fid'] = fid
                except (TypeError, ValueError) as ex:
                    log.error('Skipping Entry: %s, could not parse fid string: %s, error: %s', new_entry, fid_string, ex)
                    continue
            if xml_entry.updated_parsed:
                new_entry['rss_pubdate'] = datetime.fromtimestamp(mktime(xml_entry.updated_parsed))
            elif xml_entry.updated:
                parsed_date = str_to_naive_utc(xml_entry.updated)
                if parsed_date:
                    new_entry['rss_pubdate'] = parsed_date

            # copy xml attribute namespace data to entry
            new_entry.update_using_map(field_map, xml_entry, ignore_none=True, ignored_values=['Raw/Unknown', 'N/A', 'Unchecked'])
            if config['valid_only'] is True:
                if not all(key in new_entry for key in field_validation_list):
                    continue
            # now manually fix known fields
            # 344.18 MB (360.895.922)
            size_string = self.get_value_via_regex('anidb_feed_size', new_entry, r'\((([0-9]{1,3}\.|[0-9]{1,3}){1,5})\)')
            if size_string:
                bytes_string = size_string.replace('.', '')
                try:
                    size_bytes = int(bytes_string)
                    size_mb = int(size_bytes / 1024 / 1024)  # MB
                    if size_mb > 0:
                        new_entry['content_size'] = size_mb  # FIXME: is this valid here or put in 'anidb'?
                        new_entry['anidb_feed_size'] = size_bytes  # update with parsed size
                except ValueError as ex:
                    log.warning('Could not extract valid size from string: %s, error: %s', size_string, ex)
            # "HorribleSubs (HorribleSubs)"
            group_tag = self.get_value_via_regex('anidb_feed_group', new_entry, r'\((.*?)\)')
            # "title - 1 - ... - Complete Movie"
            # FIXME: 'Complete Movie' is not guaranteed?
            is_movie = self.get_value_via_regex('title', new_entry, r'- .*?(Complete Movie)$')
            # 1920x1080, 848x480, 1280x720
            resolution_string = self.get_value_via_regex('anidb_feed_resolution', new_entry, r'x([0-9]{3,4})$')
            source_string = None
            if new_entry.get('anidb_feed_source'):
                source_string = ANIDB_SOURCES_MAP.get(new_entry['anidb_feed_source'])
            # 'Matches official CRC (9833055b)'
            if new_entry.get('anidb_feed_crc_status'):
                crc_string = self.get_value_via_regex('anidb_feed_crc_status', new_entry,
                                                      r'Matches official CRC \((([0-9]|[A-Fa-f]){8,8})\)')
                if crc_string:
                    new_entry['anidb_file_crc32'] = crc_string.lower()
            # "title - 6 - episode name - [group_tag]... or (344.18 MB)"
            anidb_name = self.get_value_via_regex('title', new_entry, r'^(.*?) -')
            anidb_name = anidb_name.rstrip()
            if not anidb_name:
                log.error('Skipping entry, invalid anidb name parsed from: %s', new_entry['title'])
                continue

            # fix and add to new_entry()
            quality_string = ''
            if resolution_string:
                quality_string += resolution_string
            if source_string:
                quality_string += ' ' + source_string
            quality_string = quality_string.strip()
            if quality_string:
                new_entry['quality'] = Quality(quality_string)
            # build the new 'title' mimic general scene naming convention
            title_new = anidb_name
            if is_movie is not None:
                new_entry['movie_name'] = anidb_name
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
            if group_tag:
                title_new += ' [%s]' % group_tag  # TODO: do we always add group?
                new_entry['anidb_feed_grouptag'] = group_tag
            if new_entry.get('quality') and hasattr(new_entry['quality'], 'resolution'):
                if new_entry['quality'].resolution.name != 'unknown':
                    title_new += ' [%s]' % new_entry['quality'].resolution

            new_entry['title'] = title_new
            new_entry['anidb_name'] = anidb_name
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
