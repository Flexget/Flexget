import codecs
import os
import re

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

logger = logger.bind(name='regexp_parse')


class RegexpParse:
    r"""This plugin is designed to take input from a web resource or a file.
    It then parses the text via regexps supplied in the config file.

    source: is a file or url to get the data from. You can specify a username:password

    sections: Takes a list of dicts that contain regexps to split the data up into sections.
    The regexps listed here are used by find all so every matching string in the data will be
    a valid section.

    keys: hold the keys that will be set in the entries

    key:
      regexps: a list of dicts that hold regexps. The key is set to the first string that matches
      any of the regexps listed. The regexps are evaluated in the order they are supplied so if a
      string matches the first regexp none of the others in the list will be used.

      required: a boolean that when set to true will only allow entries that contain this key
      onto the next stage. url and title are always required no matter what you do (part of flexget)

      #TODO: consider adding a set field that will allow you to set the field if no regexps match

      #TODO: consider a mode field that allows a growing list for a field instead of just setting to
            # first match

    Example config

    regexp_parse:
      source: http://username:password@ezrss.it/feed/
      encoding: "utf-8"
      sections:
        - {regexp: "(?<=<item>).*?(?=</item>)", flags: "DOTALL,IGNORECASE"}

      keys:
        title:
          regexps:
            - {regexp: '(?<=<title><!\[CDATA\[).*?(?=\]\]></title>)'} #comment
        url:
          regexps:
            - {regexp: "magnet:.*?(?=])"}
        custom_field:
          regexps:
            - {regexp: "custom regexps", flags: "comma separated list of flags (see python regex docs)"}
          required: False
        custom_field2:
          regexps:
            - {regexp: 'first custom regexps'}
            - {regexp: 'can't find first regexp so try this one'}
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
            }
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
            'sections': {'$ref': '#/definitions/regex_list'},
            'keys': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'object',
                    'properties': {
                        'required': {'type': 'boolean'},
                        'regexps': {'$ref': '#/definitions/regex_list'},
                    },
                    'required': ['regexps'],
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
            COMBIND_FLAGS = COMBIND_FLAGS | RegexpParse.FLAG_VALUES[flag.strip()]
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

    @cached('regexp_parse')
    @plugin.internet(logger)
    def on_task_input(self, task, config):
        url = config['source']
        encoding = config.get('encoding')

        # if it's a file open it and read into content (assume utf-8 encoding)
        if os.path.isfile(os.path.expanduser(url)):
            content = codecs.open(url, 'r', encoding=encoding or 'utf-8').read()
        # else use requests to get the data
        else:
            resp = task.requests.get(url)
            if encoding:
                resp.encoding = encoding
            content = resp.text

        sections = []
        seperators = config.get('sections')
        if seperators:
            for sep in seperators:
                flags = 0
                if 'flags' in sep:
                    flags = self.flagstr_to_flags(sep['flags'])
                sections.extend(re.findall(sep['regexp'], content, flags))

        # no seperators just do work on the whole content
        else:
            sections.append(content)

        # holds all the regex in a dict for the field they are trying to fill
        key_to_regexps = {}

        # put every key in keys into the rey_to_regexps list
        for key, value in config['keys'].items():
            key_to_regexps[key] = self.compile_regexp_dict_list(value['regexps'])
            if 'required' in value and value['required']:
                self.required.append(key)

        entries = []
        for section in sections:
            entry = Entry()
            for key, regexps in key_to_regexps.items():
                for regexp in regexps:
                    m = regexp.search(section)
                    if m:
                        entry[key] = m.group(0)
                        break
            if self.isvalid(entry):
                entries.append(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(RegexpParse, 'regexp_parse', api_ver=2)
