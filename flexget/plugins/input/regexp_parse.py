from __future__ import unicode_literals, division, absolute_import
import re
import logging
import os
from flexget.entry import Entry
from flexget.utils.cached_input import cached
from flexget.plugin import register_plugin, internet

log = logging.getLogger('regexp_parse')


class RegexpParse(object):

    FLAG_VALUES = {'DEBUG': re.DEBUG,
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
                   'VERBOSE': re.VERBOSE
                   }

    def __init__(self):
        self.required = []

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')

        root.accept('url', key='resource', required=True)
        root.accept('file', key='resource', required=True)

        title_regex_list = root.accept('list', key='title', required=True)
        title_regex = title_regex_list.accept('dict', requiered=True)
        title_regex.accept('regexp', key='regex', required=True)
        title_regex.accept('text', key='flags')

        link_regex_list = root.accept('list', key='url', required=True)
        link_regex = link_regex_list.accept('dict', required=True)
        link_regex.accept('regexp', key='regex', required=True)
        link_regex.accept('text', key='flags')

        section_regex_list = root.accept('list', key='sections')
        section_regex = section_regex_list.accept('dict', required=True)
        section_regex.accept('regexp', key='regex', required=True)
        section_regex.accept('text', key='flags')

        custom_keys = root.accept('dict', key='custom-keys')
        key = custom_keys.accept_any_key('dict')
        key.accept('boolean', key='required')
        regex_list = key.accept('list', key='regexs', required=True)
        regex = regex_list.accept('dict', required=True)
        regex.accept('regexp', key='regex', required=True)
        regex.accept('text', key='flags')

        return root

    def flagstr_to_flags(self, flag_str):
        COMBIND_FLAGS = 0
        split_flags = flag_str.split(',')
        for flag in split_flags:
            COMBIND_FLAGS = COMBIND_FLAGS | RegexInput.FLAG_VALUES[flag.strip()]
        return COMBIND_FLAGS

    def compile_regex_dict_list(self, re_list):
        compiled_regexs = []
        for dic in re_list:
            flags = 0
            if 'flags' in dic:
                flags = self.flagstr_to_flags(dic['flags'])
            compiled_regexs.append(re.compile(dic['regex'], flags))
        return compiled_regexs

    def isvalid(self, entry):
        for key in self.required:
            if key not in entry:
                return False
        return entry.isvalid()

    @cached('text')
    @internet(log)
    def on_task_input(self, task, config):

        url = config['resource']

        ##if it's a file open it and read into content
        if os.path.isfile(os.path.expanduser(url)):
            content = open(url).read()
        else:
            content = task.requests.get(url).text

        sections = []
        seperators = config.get('sections')
        if seperators:
            for sep in seperators:
                flags = 0
                if 'flags' in sep:
                    flags = self.flagstr_to_flags(sep['flags'])
                sections.extend(re.findall(sep['regex'], content, flags))

        #no seperators just do work on the whole content
        else:
            sections.append(content)

        #holds all the regex in a dict for the field they are trying to fill
        key_to_regexs = {}
        key_to_regexs['title'] = self.compile_regex_dict_list(config.get('title'))
        key_to_regexs['url'] = self.compile_regex_dict_list(config.get('url'))

        custom_keys = config.get('custom-keys')

        if custom_keys:
            for key, value in custom_keys.iteritems():
                key_to_regexs[key] = self.compile_regex_dict_list(value['regexs'])
                if 'required' in value and value['required']:
                    self.required.append(key)

        entries = []
        for section in sections:
            entry = Entry()
            for key, regexs in key_to_regexs.iteritems():
                for regex in regexs:
                    m = regex.search(section)
                    if m:
                        entry[key] = m.group(0)
                        break
            if self.isvalid(entry):
                entries.append(entry)

        return entries


register_plugin(RegexpParse, 'regexp_parse', api_ver=2)
