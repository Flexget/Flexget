"""Plugin for json file."""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import re
import os
import logging

import glob
import path

from flexget import plugin
from flexget.utils import json
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('json')


class Json(object):
    """
    Parse a json file for entries using regular expression.

    Example:: 

      file: <path to JSON file>
      entry:
        <field>: <corresponding JSON key>

    Note: each entry must have at least two fields, 'title' and 'url'. If not specified in the config, 
    this plugin asssumes that keys named 'title' and 'url' exist within the JSON.

    Example::

      json:
        file: entries.json
        encoding: utf8
        entry:
          title: 'name'
          url: "web_address"
    """
    

    schema = {
        'type': 'object',
        'properties': {
            'files': {'type': 'string'},
            'encoding': {'type': 'string', 'default': 'utf-8'},
            'entry': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'type': 'string'},
                        {
                            'type': 'object',
                            'additionalProperties': {
                                'type': 'string', 'format': 'regex'
                            },
                        },
                    ]
                },
            },
        },
        'required': ['files'],
        'additionalProperties': False,
    }
                    

    def on_task_input(self, task, config):
        files = os.path.expanduser(config['files'])
        json_encoding = config['encoding']
        entry_config = config.get('entry')
        
        fields = {}
        get_remnants = False
        if config.get('entry'):
            for required_field in config.get('entry'):
                if isinstance(required_field, str):
                    if required_field == 'get_remnants':
                        get_remnants = True
                    else:
                        fields[required_field] = required_field
                else:
                    fields[next(iter(required_field))] = re.compile("^" + required_field[next(iter(required_field))] + "$")
                        
            if 'title' not in fields.keys():
                fields['title'] = re.compile("^title$")
            if 'url' not in fields.keys():
                fields['url'] = re.compile("^url$")

        entries = []
        entry = Entry()
        
        list_of_files = glob.glob(files)
        if not list_of_files:
            log.warning('No JSON file(s) found in the path specified in the config file.')
        for filename in list_of_files:
            with open(filename, encoding=json_encoding) as json_file:
                json_dict = json.load(json_file)
            for entry_title in json_dict:
                all_entry_fields = json_dict[entry_title]
                for entry_field in all_entry_fields:
                    if not entry_config:
                        entry[entry_field] = all_entry_fields[entry_field] # de-serialize here?
                    else:
                        for key in fields:
                            match = re.search(fields[key], entry_field)
                            if match:
                                entry[key] = all_entry_fields[match.group(0)] # de-serialize here?
                        if entry_field not in fields.keys() and get_remnants:
                            entry[entry_field] = all_entry_fields[entry_field] # de-serialize here?

                if not entry.isvalid():
                    log.info(
                        'Invalid data, constructed entry is missing mandatory fields (title or url)'
                    )
                else:
                    entries.append(entry)
                    log.debug('Added entry %s' % entry)
                    # start new entry
                    entry = Entry()
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Json, 'json', api_ver=2)
