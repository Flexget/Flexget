from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib import parse

import codecs
import re
import logging
import os
import zlib

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached

log = logging.getLogger('soup_parse')


class SoupParse(object):
    """This plugin is designed to take html input from a web resource or a file.
    It then parses the text via BeautifulSoup (and optional regexps) supplied in the config file.

    source: This is a file location or url to get the data from. You can specify a username:password.

    sections: Takes a list of dicts that contain options for searching with BeautifulSoup. These options 
    include html element names, html attribute names, html attribute values, as well as starting and 
    ending points for the returned tag matches. These are used to recursively search within the specified tags,
    and split the data up into sections.  The options that are listed here are used by 'find_all', so every 
    matching html tag in the data will be a valid section. All keys specified below must be found in each 
    respective section.

    keys: hold the keys that will be set in the entries.

    key:
      section: Identical to 'sections' above. However, instead of searching on the whole file/webpage, 
      the search will begin in each of the already found sections. If 'section' is absent from the key, 
      the location specified below will be applied to the section from the 'sections' area of the config.
      
      location: Takes a string (either 'text' or 'url') or a dict that contains a key named 'text' or 'url' with 
      an integer as the value. This is used when there are multiple 'text' or 'url' keys in the html tag. 
      It allows you to spcify which match to choose. If the string 'text' or 'url' is used, it defaults to 
      the first match. If 'location' is absent from the key, it defaults to the first 'text' match.

      regexps: a list of dicts that hold regexps. The key is set to the first string that matches
      any of the regexps listed. The regexps are evaluated in the order they are supplied so if a
      string matches the first regexp none of the others in the list will be used.
      
      default_value: a string that will be used as the default value for all keys have no matching info.
      It can contain references to other keys that are listed above it. If default value is used here and
      in a key, the default_value under the key will take precedence. Reference other key by enclosing in 
      double curly braces.

      required: a boolean that when set to true will only allow entries that contain this key
      onto the next stage. 'url' and 'title' are always required no matter what you do (part of flexget)

      #TODO: consider adding a set field that will allow you to set the field if no regexps match

      #TODO: consider a mode field that allows a growing list for a field instead of just setting to
            # first match

    Example config

    soup_parse:
      source: http://username:password@ezrss.it/feed/
      default_value: foofighters
      sections:
        - body
        - element_name: section
          start: 2
          end: 11
        - element_name: div
          attribute_name: class
          attribute_value: media_info
      keys:
        title:
          section:
            - element_name: a
        url:
          section:
            - element_name: a
          location: url
        datetime:
          section:
            - element_name: span
              attribute_name: class
              attribute_value: datetime
          location: text
          regexps:
            - regexp: '[SMTWF].*?ET'
            - regexp: '[SMTWF].*?\d\d\d\d'
        custom_field1:
        default_value: 'www.coolsite.com/page/{{title}}/info'
          section:
            - element_name: span
              attribute_name: class
              attribute_value: foo
          regexps:
            - regexp: '(?<=stuff_before).*?(?=stuff_after)'
              flags: 'DOTALL,IGNORECASE'
          location:
            text: 2
        custom_field2:
          regexps:
            - regexp: 'first custom regexp'
              flags: 'DOTALL,IGNORECASE'
            - regexp: 'can't find first regexp so try this one'
              flags: 'DOTALL,IGNORECASE'


    """

    # dict used to convert string values of regexp flags to int
    FLAG_VALUES = {
        'DEBUG': re.DEBUG,
        'I': re.I,
        'IGNORECASE': re.IGNORECASE,
        'L': re.L,
        'LOCALE': re.LOCALE,
        'M': re.M,
        'MULTILINE': re.MULTILINE,
        'S': re.S,
        'DOTALL': re.DOTALL,
        'U': re.U,
        'UNICODE': re.UNICODE,
        'X': re.X,
        'VERBOSE': re.VERBOSE,
    }

    FLAG_REGEX = r'^(\s?({})\s?(,|$))+$'.format('|'.join(FLAG_VALUES))

    schema = {
        'definitions': {
            'scope_limiter': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'type': 'string'},
                        {
                            'type': 'object',
                            'properties': {
                                'element_name': {'type': 'string'},
                                'attribute_name': {'type': 'string'},
                                'attribute_value': {'type': 'string'},
                                'start': {'type': 'integer', 'default': 1, 'minimum': 1},
                                'end': {'type': 'integer', 'default': 31415, 'minimum': 1},
                            },
                            'additionalProperties': False,
                            'anyOf': [
                                {'required': ['element_name']},
                                {'required': ['attribute_name']},
                                {'required': ['attribute_value']},
                            ],
                            'dependencies': {'attribute_value': ['attribute_name']},
                        },
                    ]
                },
            },
            'regex_list': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'regexp': {'type': 'string', 'format': 'regex'},
                        'flags': {
                            'type': 'string',
                            'pattern': FLAG_REGEX,
                            'error_pattern': 'Must be a comma separated list of flags. See python regex docs.',
                        },
                    },
                    'required': ['regexp'],
                    'additionalProperties': False,
                },
            },
        },
        'type': 'object',
        'properties': {
            'source': {
                'anyOf': [
                    {'type': 'string', 'format': 'url'},
                    {'type': 'string', 'format': 'file'},
                ]
            },
            'encoding': {'type': 'string'},
            'default_value': {'type': 'string'},
            'sections': {'$ref': '#/definitions/scope_limiter'},
            'keys': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'object',
                    'properties': {
                        'default_value': {'type': 'string'},
                        'section': {'$ref': '#/definitions/scope_limiter'},
                        'location': {
                            'oneOf': [
                                {'type': 'string', 'enum': ['text', 'url']},
                                {
                                    'type': 'object',
                                    'properties': {
                                        'text': {'type': 'integer', 'minimum': 1},
                                        'url': {'type': 'integer', 'minimum': 1},
                                    },
                                    'additionalProperties': False,
                                    'oneOf': [
                                        {'required': ['text']},
                                        {'required': ['url']},
                                    ]
                                },
                            ]
                        },
                        'required': {'type': 'boolean'},
                        'regexps': {'$ref': '#/definitions/regex_list'},
                    },
                    'additionalProperties': False,
                },
                'required': ['title', 'url'],
            },
        },
        'required': ['source', 'keys'],
        'additionalProperties': False,
    }

    def __init__(self):
        self.required = []

    def flagstr_to_flags(self, flag_str):
        """turns a comma seperated list of flags into the int value."""
        COMBIND_FLAGS = 0
        split_flags = flag_str.split(',')
        for flag in split_flags:
            COMBIND_FLAGS = COMBIND_FLAGS | SoupParse.FLAG_VALUES[flag.strip()]
        return COMBIND_FLAGS

    def compile_regexp_dict_list(self, re_list):
        """turns a list of dicts containing regexps information into a list of compiled regexps."""
        compiled_regexps = []
        for dic in re_list:
            flags = 0
            if 'flags' in dic:
                flags = self.flagstr_to_flags(dic['flags'])
            compiled_regexps.append(re.compile(dic['regexp'], flags))
        return compiled_regexps

    def isvalid(self, entry):
        """checks to make sure that all required fields are present in the entry."""
        for key in self.required:
            if key not in entry:
                return False
        return entry.isvalid()

    def _get_master_tag_list(self, element_tag_list, scope_num, tag_search_terms):
        
        temp_list = []
        for x in range(len(element_tag_list[scope_num])):
            new_tag_list = (
                element_tag_list[scope_num][x].find_all(tag_search_terms[scope_num][0], 
                                                        tag_search_terms[scope_num][1])
            )
            if (eval(tag_search_terms[scope_num][2]) >= eval(tag_search_terms[scope_num][3]) or
                eval(tag_search_terms[scope_num][2]) >= len(new_tag_list)):
                log.warning(
                    ("The specified start (%s) for scope_limit #%s is the same as or after the specified end (%s)"
                        " or actual end (%s) for match #%s. The start will be set to the beginning, by default.") % (
                        str(eval(tag_search_terms[scope_num][2]) + 1), str(scope_num + 1),
                        str(eval(tag_search_terms[scope_num][3])), str(len(new_tag_list)), str(x + 1))
                )
                start = "0"
            else:
                start = tag_search_terms[scope_num][2]
            if eval(tag_search_terms[scope_num][3]) > len(new_tag_list):
                log.warning(
                    ("The specified end (%s) for scope_limit #%s is after the actual end (%s) for match #%s. The "
                        "end will be set to the actual end, by default.") % (
                        str(eval(tag_search_terms[scope_num][3])), str(scope_num + 1), str(len(new_tag_list)), str(x + 1))
                )
                end = str(len(new_tag_list))
            else:
                end = tag_search_terms[scope_num][3]
            for y in range(eval(start), eval(end)):
                temp_list.append(new_tag_list[y])
        
        if scope_num + 1 < len(tag_search_terms):
            element_tag_list.append(temp_list)
            return self._get_master_tag_list(element_tag_list, scope_num + 1, tag_search_terms)
        else:
            return temp_list

    def _tag_limiter(self, config, scope_limits):

        tag_search_terms = []
        for limit in scope_limits:
            if isinstance(limit, str):
                el_name = re.compile("^" + limit + "$")
                att_dict = {}
                start = "0"
                end = "len(new_tag_list)"
            else:
                el_name = limit.get('element_name')
                att_name = limit.get('attribute_name')
                att_val = limit.get('attribute_value')
                start = str(limit.get('start') - 1)
                end = limit.get('end')
                if not el_name:
                    el_name = '.*'
                el_name = re.compile("^" + el_name + "$")
                if not att_name and not att_val:
                    att_dict = {}
                else:
                    if not att_val:
                        att_val = '.*'
                    att_dict = {att_name: re.compile("^" + att_val + "$")}
                if end == 31415:
                    end = "len(new_tag_list)"
                else:
                    end = str(end)
            tag_search_terms.append([el_name, att_dict, start, end])
        return tag_search_terms
            
    @cached('soup_parse')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        url = config['source']
        encoding = config.get('encoding')
        
        # holds all the regex in a dict for the field they are trying to fill
        key_to_regexps = {}
        
        # put every key in keys into the key_to_regexps list
        for key, value in config['keys'].items():
            if 'regexps' in value:
                regexps = value['regexps']
            else:
                regexps = [{'regexp': '.*'}]
            key_to_regexps[key] = self.compile_regexp_dict_list(regexps)
            if 'required' in value and value['required']:
                self.required.append(key)

        # if it's a file open it and read into content (assume utf-8 encoding)
        if os.path.isfile(os.path.expanduser(url)):
            soup = get_soup(codecs.open(url, 'r', encoding=encoding or 'utf-8').read())
        # else use requests to get the data
        else:
            log.verbose('Requesting: %s' % url)
            page = task.requests.get(url)
            log.verbose('Response: %s (%s)' % (page.status_code, page.reason))
            if encoding:
                page.encoding = encoding
            soup = get_soup(page.content)
        scope_limits = config.get('sections')
        if scope_limits:
            tag_search_terms = self._tag_limiter(config, scope_limits)
            sections = self._get_master_tag_list([[soup]], 0, tag_search_terms)
        else:
            sections = [soup]

        return self.create_entries(url, sections, key_to_regexps, config)

    def get_def_val(self, default, entry):
        if re.search(r'.*{{.*?}}.*', default):
            def_key = re.sub(r'.*?{{(.*?)}}.*', r'\1', default)
            try:
                def_var = entry[def_key]
                default = re.sub(r'{{.*?}}', def_var, default)
                return default
            except KeyError:
                log.warning('Could not substitute default value. Key "%s" does not exist in this entry.' % def_key)
                return False
        else:
            return default
            
    def create_entries(self, url, sections, key_to_regexps, config):
        
        def title_exists(title):
            """Helper method. Return True if title is already added to entries"""
            for entry in queue:
                if entry['title'] == title:
                    return True
        def not_found(default):
            if default:
                log.warning("Applying default value.")
                return default
            else:
                log.warning("Skipping to next key search.")
                return False            
            
                
        queue = []
        sec_num = 0
        for section in sections:
            sec_num += 1
            entry = Entry()
            
            for key, value in config['keys'].items():
                if 'default_value' in value:
                    default = self.get_def_val(value['default_value'], entry)
                elif 'default_value' in config.keys():
                    default = self.get_def_val(config['default_value'], entry)
                else:
                    default = False
                if 'section' in value:
                    scope_limits = value['section']
                else:
                    scope_limits = ''
                if 'location' in value:
                    location_info = value['location']
                else:
                    # If no location is specified, assume the wanted value is in the first 'text' area of the tag.
                    location_info = 'text'
                if scope_limits:
                    tag_search_terms = self._tag_limiter(config, scope_limits)
                    tag_list = self._get_master_tag_list([[section]], 0, tag_search_terms)
                    if tag_list:
                        tag = tag_list
                    else:
                        log.warning("The specified 'section' for key: '" + str(key) + 
                                    "' was not found inside of the its parent tag in section #" + 
                                    str(sec_num))
                        default = not_found(default)
                        if not default:
                            continue
                        tag = [get_soup('<a href="' + default + '">' + default + '</a>', 'html.parser').find('a')]
                else:
                    # If the scope isn't limited, get the 'text' or 'url' from the main sections.
                    tag = section
                if isinstance(location_info, str):
                    if location_info == 'text':
                        new_section = tag[0].text.strip()
                    else:
                        try:
                            new_section = tag[0].find('a')['href']
                            if not new_section.startswith('http://') or not new_section.startswith('https://'):
                                new_section = parse.urljoin(url, new_section)
                        except (KeyError, TypeError) as e:
                            log.warning("No url was found for key: '" + str(key) + "' in section #" +str(sec_num) + ".")
                            new_section = not_found(default)
                            if not new_section:
                                continue

                else:
                    location = next(iter(location_info))
                    loc = location_info[location]
                    if isinstance(loc, int):
                        loc = loc - 1
                    new_section = ''
                    if location == 'text':
                        contents_list = [t.text.strip() for t in tag if t.text.strip()]
                        if contents_list:
                            if len(contents_list) > loc:
                                new_section = contents_list[loc]
                            else:
                                log.warning("The specified text location for key: '" + str(key) + 
                                            "' was out of range in section #" + str(sec_num)                                            )
                                new_section = not_found(default)
                                if not new_section:
                                    continue

                        else:
                            log.warning("There was no text found at any location for key: '" + str(key) + 
                                        "' in section #")
                            new_section = not_found(default)
                            if not new_section:
                                continue
                    else:
                        contents_list = []
                        for t in tag:
                            contents_list.extend(t.find_all('a'))
                        if contents_list:
                            if len(contents_list) > loc:
                                new_section = contents_list[loc]['href']
                            else:
                                log.warning("The specified url location for key: '" + str(key) + 
                                            "' was out of range in section #" + str(sec_num)
                                            )
                                new_section = not_found(default)
                                if not new_section:
                                    continue

                        else:
                            log.warning("There were no urls found at any location for key: '" + str(key) + 
                                        "' in section #" + str(sec_num)
                                        )
                            new_section = not_found(default)
                            if not new_section:
                                continue

                regexps = key_to_regexps[key]
                for regexp in regexps:
                    # Prevent empty strings from being added as key value when no regex is specified.
                    if not new_section:
                        break
                    m = regexp.search(new_section)
                    if m:
                        value = m.group(0)
                        if key == 'title':
                            if title_exists(value):
                                # title link should be unique, add CRC32 to end if it's not
                                hash = zlib.crc32(url.encode("utf-8"))
                                crc32 = '%08X' % (hash & 0xFFFFFFFF)
                                value = '%s [%s]' % (value, crc32)
                                # truly duplicate, title + url crc already exists in queue
                                if title_exists(value):
                                    continue
                                log.debug('uniqued title to %s' % value)
                        entry[key] = value
                        break
            if self.isvalid(entry):
                queue.append(entry)

        return queue


@event('plugin.register')
def register_plugin():
    plugin.register(SoupParse, 'soup_parse', api_ver=2)
