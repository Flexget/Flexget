from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
from xml.dom import minidom

import feedparser
from time import mktime
from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tz
from datetime import datetime

from flexget.config_schema import one_or_more

from flexget.utils.qualities import Quality
from past.builtins import basestring
from flexget.utils.tools import str_to_boolean

from flexget import plugin
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.requests import TimedLimiter


log = logging.getLogger('anidb_feed')

HEADER = {'User-agent': 'Mozilla/5.0'}  # anidb needs valid header or we get '403 Client Error'
LIMITER = TimedLimiter('anidb.net', '2 seconds')  # default anidb api limit


NAMESPACE_NAME = 'xhtml'
NAMESPACE_URL = 'http://www.w3.org/1999/xhtml'
NAMESPACE_TAGNAME = 'dl'
NAMESPACE_PREFIX_MAIN = 'anidb_'
NAMESPACE_PREFIX = 'anidb_feed_'

# NOTE: all lowercase only
NAMESPACE_ATTRIBUTE_MAP = {
    'added': datetime,
    'source': basestring,
    'resolution': basestring,
    'crc_status': basestring,
    'language': basestring,
    'group': basestring,
    'subtitle_language': basestring,
    'priority': basestring,
    'quality': basestring,
    'size': basestring
}

VALIDATION_LIST = [
    'source',
    'resolution',
    'group',
    'size'
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


class AnidbFeed(object):
    """ Creates an entry for each movie or series in the AniDB notification feed.
        Your personalized notification feed url is shown under [Account/Settings/Notifications/link to your personal atom feed]
        See: https://wiki.anidb.net/w/Notifications
        The general main anidb feed can also be used url: http://anidb.net/feeds/files.atom

        Example:
            anidb_feed:
                url: http://anidb.net/perl-bin/animedbfeed.pl?id=xxxxx................
                valid_only: yes

            # valid_only: yes
            # If enabled only 'valid' entries are returned, that have a size, release group, resolution and source field
            # This happens after the file was added to anidb and has passed some initial tests/parsing

            # priority: can be one of (all, medium-high, high), which are the anidb notification priorities

            #include: include none regular files also 'special', 'op-ending', 'trailer-promo'
            anidb_feed:
                url: http://anidb.net/perl-bin/animedbfeed.pl?id=xxxxx................
                include: special

        Adds those extra Entry fields if found:
        'content_size'
        'rss_pubdate'
        'anidb_fileversion'     # fileversion aka v1-5
        'anidb_fid'             # anidb file_id
        'anidb_feed_added'
        'anidb_feed_source'
        'anidb_feed_resolution'
        'anidb_feed_crc_status'
        'anidb_feed_language'
        'anidb_feed_group'
        'anidb_feed_subtitle_language'
        'anidb_feed_priority'
        'anidb_feed_quality'
        'anidb_feed_size'
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
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

    # notification update interval is 15 minutes
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
            if config['priority'] is 'medium-high':
                priority = 1
            elif config['priority'] is 'high':
                priority = 2
            priority_fragment = '&pri=%s' % priority
        return self.fill_entries_for_url(url + priority_fragment, task, config)

    @staticmethod
    def is_valid_entry(entry, ns_prefix_name=''):
        for key in VALIDATION_LIST:
            key_name = ns_prefix_name + key
            if not entry.get(key_name):  # int(0) is invalid
                return False
            elif entry[key_name] in ['Raw/Unknown', 'N/A', 'Unchecked']:
                return False
        return True

    def get_value_via_regex(self, key, entry, re_string, group_nr=1):
        result = None
        if entry.get(key):
            value_string = entry[key]
            if isinstance(value_string, basestring) and not value_string.isspace():
                match = re.search(re_string, value_string)
                if match and match.group(group_nr) and not match.group(group_nr).isspace():
                    result = match.group(group_nr)
            else:
                log.error('Expecting string for re lookup got: %s, tyep: %s' % (value_string, type(value_string)))
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
            except Exception as ex:
                ep_nr = None
                log.warning('Expecting a episode nr as integer in: %s, error: %s' % (entry[key], ex))
        if file_version:
            try:
                file_version = int(file_version)
            except Exception as ex:
                file_version = None
                log.warning('Expecting a file version nr as integer in: %s, error: %s' % (entry[key], ex))
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
            if xml_entry.id:
                guid_splits = re.split('[/=]', xml_entry.id)
                new_entry[NAMESPACE_PREFIX_MAIN + 'fid'] = guid_splits.pop()  # andidb file id
            if xml_entry.updated_parsed:
                new_entry['rss_pubdate'] = datetime.fromtimestamp(mktime(xml_entry.updated_parsed))
            elif xml_entry.updated:
                parsed_date = convert_to_naive_utc(xml_entry.updated)
                if parsed_date:
                    new_entry['rss_pubdate'] = parsed_date

            # add some usefully attributes to the namespace
            self.fill_namespace_attributes(xml_entry, new_entry)
            if config['valid_only'] is True:
                if self.is_valid_entry(new_entry, NAMESPACE_PREFIX) is False:
                    continue
            # now manually fix known fields
            # 344.18 MB (360.895.922)
            size_string = self.get_value_via_regex(NAMESPACE_PREFIX + 'size', new_entry, r'\((([0-9]{1,3}\.|[0-9]{1,3}){1,5})\)')
            if size_string:
                bytes_string = size_string.replace('.', '')
                try:
                    size_mb = int(int(bytes_string) / 1024 / 1024)  # MB
                    if size_mb > 0:
                        new_entry['content_size'] = size_mb  # FIXME: is this valid here or put in NAMESPACE_PREFIX_MAIN?
                except Exception as ex:
                    log.warning('Could not extract valid size from string: %s, error: %s' % (size_string, ex))
            # "HorribleSubs (HorribleSubs)"
            group_tag = self.get_value_via_regex(NAMESPACE_PREFIX + 'group', new_entry, r'\((.*?)\)')
            # "title - 1 - ... - Complete Movie"
            # FIXME: 'Complete Movie' is not guaranteed?
            is_movie = self.get_value_via_regex('title', new_entry, r'- .*?(Complete Movie)$')
            # 1920x1080, 848x480, 1280x720
            resolution_string = self.get_value_via_regex(NAMESPACE_PREFIX + 'resolution', new_entry, r'x([0-9]{3,4})$')
            source_string = None
            if new_entry.get(NAMESPACE_PREFIX + 'source'):
                source_string = ANIDB_SOURCES_MAP.get(new_entry[NAMESPACE_PREFIX + 'source'])
            # "title - 6 - episode name - [group_tag]... or (344.18 MB)"
            title_name = self.get_value_via_regex('title', new_entry, r'^(.*?) -')
            # fix and add to new_entry()
            if episode_data.get('version'):
                new_entry[NAMESPACE_PREFIX_MAIN + 'fileversion'] = episode_data['version']  # TODO: Is there a official field?

            quality_string = ''
            if resolution_string:
                quality_string += resolution_string
            if source_string:
                quality_string += ' ' + source_string
            if not quality_string.isspace():
                try:
                    quality = Quality(quality_string)
                    new_entry['quality'] = quality
                except Exception as ex:
                    log.error('Could not get Quality from string: %s, error: %s' % (quality_string, ex))
            # build the new 'title' mimic general scene naming convention
            title_new = '%s ' % title_name
            if is_movie is not None:
                new_entry['movie_name'] = title_name
            else:
                new_entry['series_name'] = title_name
            if 'ep' in episode_data:
                new_entry['series_episode'] = episode_data['ep']
                title_new += '- %s' % episode_data['ep']  # FIXME: is there a valid way to encode anime episodes?
                new_entry['series_id'] = '%02d' % episode_data['ep']  # Is this valid aka a single Integer?
                if episode_data['ep'] > 99:
                    new_entry['series_id'] = '%03d' % episode_data['ep']
            elif episode_data['extra'] is True:
                extra_string = episode_data.get('special', '')
                extra_string += episode_data.get('op-ending', '')
                extra_string += episode_data.get('trailer-promo', '')
                title_new += '- %s' % extra_string
                new_entry['series_id'] = extra_string  # FIXME: is this the correct field for extras?
            if episode_data.get('version'):
                title_new += 'v%s' % episode_data['version']
            if group_tag is not None:
                title_new += ' - [%s]' % group_tag  # TODO: do we always add group?
            if new_entry.get('quality') and hasattr(new_entry['quality'], 'resolution'):
                if new_entry['quality'].resolution.name is not 'unknown':
                    title_new += ' [%s]' % new_entry['quality'].resolution

            # TODO: Add a custom entry.render() field, to allow customisation of final 'title'
            new_entry['title'] = title_new
            new_entry[NAMESPACE_PREFIX_MAIN + 'name'] = title_new  # used by anidb_list?
            entries.append(new_entry)
            #dump_entry(new_entry)
        return entries

    def fill_entries_for_url(self, url, task, config):
        log.verbose('Fetching %s' % url)

        try:
            r = task.requests.get(url, headers=HEADER, timeout=20)
        except Exception as ex:
            log.error("Failed fetching url: %s error: %s" % (url, ex))
            return []

        if r and r.status_code != 200:
            raise plugin.PluginError('Unable to reach anidb feed url: %s' % url)

        fixed_xml = self.make_feedparser_friendly(r.content)
        try:
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

        entries = self.parse_from_xml(parsed_xml.entries, config)
        if len(entries) == 0:
            log.verbose('No entries parsed from xml.')
        # else:
        #   dump_entry(entries[0])

        return entries

    def make_feedparser_friendly(self, data):
        try:
            dom = minidom.parseString(data)
            entries = dom.getElementsByTagName('entry')
            for entry in entries:
                items_ns = entry.getElementsByTagNameNS(NAMESPACE_URL, NAMESPACE_TAGNAME)
                if items_ns:
                    for node_ns in items_ns:
                        dt_nodes = node_ns.getElementsByTagName(NAMESPACE_NAME + ':dt')
                        dd_nodes = node_ns.getElementsByTagName(NAMESPACE_NAME + ':dd')
                        if len(dt_nodes) != len(dd_nodes):
                            logging.warning('unexpected nodecount')
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
        except Exception as ex:
            logging.debug('Unable to rename nodes in XML: %s' % ex)
            return None
        return dom.toxml()

    def set_ns_attribute(self, name, xml_entry, entry, in_ns_name, out_prefix_name=None, in_type=basestring):
        tagname = in_ns_name + '_' + name  # feedparser represents those as nsname_tagname
        value = None
        if tagname in entry and entry.get(tagname) is not None:
            value = entry.get(tagname)  # use existing, but do type check
        elif tagname in xml_entry:
            if isinstance(xml_entry[tagname], dict) and 'value' in xml_entry[tagname]:
                value = xml_entry[tagname]['value']
            elif isinstance(xml_entry[tagname], basestring):
                value = xml_entry[tagname]

        if out_prefix_name is not None and not out_prefix_name.isspace():
            tagname = out_prefix_name + name

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
            self.set_ns_attribute(key, xml_entry, entry, NAMESPACE_NAME, NAMESPACE_PREFIX, NAMESPACE_ATTRIBUTE_MAP[key])


@event('plugin.register')
def register_plugin():
    plugin.register(AnidbFeed, 'anidb_feed', api_ver=2, groups=['list'])
