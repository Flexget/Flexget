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

from flexget.utils.qualities import Quality
from past.builtins import basestring
from flexget.utils.tools import str_to_boolean

from flexget import plugin
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.entry import Entry
from flexget.utils.requests import Session, TimedLimiter


log = logging.getLogger('anidb_feed')

requests = Session()
requests.headers.update({'User-Agent': 'Mozilla/20.0'}) # needs valid header or we get '403 Client Error'
requests.add_domain_limiter(TimedLimiter('anidb.net', '2 seconds'))

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
    """"Creates an entry for each movie or series in the AniDB notification feed.
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
        },
        'additionalProperties': False,
        'required': ['url'],
    }

    # notification update interval is 15 minutes
    @cached('anidb_feed', persist='15 minutes')
    def on_task_input(self, task, config):
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
                    new_entry = None
                    continue

            # now manually fix known fields
            if new_entry.get(NAMESPACE_PREFIX + 'size'):
                size = new_entry[NAMESPACE_PREFIX + 'size']
                match = re.search(r'\((([0-9]{1,3}\.|[0-9]{1,3}){1,5})\)', size)  # 344.18 MB (360.895.922)
                if match and match.group(1):
                    bytes_string = match.group(1).replace('.', '')
                    try:
                        size_mb = int(int(bytes_string) / 1024 / 1024)  # MB
                        if size_mb > 0:
                            new_entry['content_size'] = size_mb  # FIXME: is this valid here or put in NAMESPACE_PREFIX_MAIN?
                    except Exception as ex:
                        log.warning('Could not extract valid size from string: %s, error: %s' % (bytes_string, ex))

            group_tag = None
            if new_entry.get(NAMESPACE_PREFIX + 'group'):
                group_string = new_entry[NAMESPACE_PREFIX + 'group']
                match = re.search(r'\((.*?)\)', group_string)  # "HorribleSubs (HorribleSubs)"
                if match and match.group(1) and not match.group(1).isspace():
                    group_tag = match.group(1)

            title_name = None
            match = re.search(r'^(.*?) -', new_entry['title'])  # "title - 6 - episode name - [group_tag]... or (344.18 MB)"
            if match and match.group(1) and not match.group(1).isspace():
                title_name = match.group(1)

            # FIXME: missing full v1-v5 handling!
            episode_nr = None
            version_nr = None
            match = re.search(r'^.*? - ([0-9]{1,3}) -', new_entry['title'])
            if match and match.group(1) and not match.group(1).isspace():
                try:
                    # anidb always uses absolute ep numbering, even movies get "- 1 -" !!
                    # no Cx or Sx support (opening/ending/specials) anime naming is hard enough
                    episode_nr = int(match.group(1))
                except Exception as ex:
                    log.warning('Expecting a episode nr as integer in: %s, error: %s' % (new_entry['title'], ex))
            else:
                match = re.search(r'^.*? - ([0-9]{1,3})v([0-5]) -', new_entry['title'])  # - 9v2 -
                if match and match.group(1) and not match.group(1).isspace():
                    try:
                        episode_nr = int(match.group(1))
                    except Exception as ex:
                        log.warning('Expecting a episode nr as integer in: %s, error: %s' % (new_entry['title'], ex))
                    if match and match.group(2) and not match.group(2).isspace():
                        try:
                            version_nr = int(match.group(2))
                        except Exception as ex:
                            log.warning('Expecting a version nr in: %s, error: %s' % (new_entry['title'], ex))

            is_movie = False
            match = re.search(r'- .*?(Complete Movie)$', new_entry['title'])  # "title - 1 - ... - Complete Movie"
            if match and match.group(1) and not match.group(1).isspace():
                is_movie = True  # FIXME: 'Complete Movie' is not guaranteed?

            resolution_string = None
            source_string = None
            if new_entry.get(NAMESPACE_PREFIX + 'source'):
                source_string = ANIDB_SOURCES_MAP.get(new_entry[NAMESPACE_PREFIX + 'source'])
            if new_entry.get(NAMESPACE_PREFIX + 'resolution'):
                resolution_field = new_entry[NAMESPACE_PREFIX + 'resolution']
                match = re.search(r'x([0-9]{3,4})$', resolution_field)  # 1920x1080, 848x480, 1280x720
                if match and match.group(1) and not match.group(1).isspace():
                    resolution_string = match.group(1)

            # fix and add to new_entry()
            title_new = title_name
            if version_nr is not None:
                new_entry[NAMESPACE_PREFIX_MAIN + 'fileversion'] = version_nr  # TODO: Is there a official field?

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

            if is_movie is True:
                new_entry['movie_name'] = title_name
                if version_nr is not None:
                    title_new += ' v%s' % version_nr
                if group_tag is not None:
                    title_new += ' [%s]' % group_tag  # TODO: do we always add group?
            else:
                new_entry['series_name'] = title_name
                if episode_nr is not None:
                    new_entry['series_episode'] = episode_nr
                    title_new += ' - %s' % episode_nr  # FIXME: is there a valid way to encode anime episodes?
                    if version_nr is not None:
                        title_new += 'v%s' % version_nr
                    if group_tag is not None:
                        title_new += ' - [%s]' % group_tag  # TODO: do we always add group?
                else:
                    log.error('No episode nr. found for series, should not happen: %s' % new_entry['title'])

            new_entry['title'] = title_new
            new_entry[NAMESPACE_PREFIX_MAIN + 'name'] = title_new  # used by anidb_list?
            entries.append(new_entry)
            #dump_entry(new_entry)
        return entries

    def fill_entries_for_url(self, url, task, config):
        log.verbose('Fetching %s' % url)

        try:
            r = requests.get(url, timeout=20)
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
