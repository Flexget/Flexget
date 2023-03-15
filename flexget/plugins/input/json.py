"""Plugin for json files."""
from pathlib import Path

import dateutil.parser as parser
from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json

logger = logger.bind(name='json')


class Json:
    """
    Return entries from a json file.

    ::

      file: <path to JSON file>
      encoding: <JSON encoding>
      field_map:
        - <entry field>: <corresponding JSON key>

    Note: each entry must have at least two fields, 'title' and 'url'. If not specified in the config,
    this plugin asssumes that keys named 'title' and 'url' exist within the JSON.
    'encoding' defaults to 'utf-8'

    Example::

      json:
        file: entries.json
        encoding: utf-8
        field_map:
          - title: name
    """

    schema = {
        'type': 'object',
        'properties': {
            'file': {'type': 'string', 'format': 'file'},
            'encoding': {'type': 'string'},
            'field_map': {'type': 'object', 'additionalProperties': {'type': 'string'}},
        },
        'required': ['file'],
        'additionalProperties': False,
    }

    @staticmethod
    def ds_dt(val):
        try:
            return parser.parse(val)
        except (ValueError, OverflowError):
            return val

    def on_task_input(self, task, config):
        file = Path(config['file'])
        field_map = config.get('field_map', {})
        # Switch the field map to map from json to flexget fields
        field_map = {v: k for k, v in field_map.items()}
        with file.open(encoding=config.get('encoding', 'utf-8')) as data:
            contents = json.load(data)
            for item in contents:
                entry = Entry()
                for field, value in item.items():
                    if field in field_map:
                        entry[field_map[field]] = self.ds_dt(value)
                    else:
                        entry[field] = self.ds_dt(value)
                if not entry.isvalid():
                    logger.error(
                        'No title and url defined for entry, you may need to use field_map to map them.'
                    )
                yield Entry(item)


@event('plugin.register')
def register_plugin():
    plugin.register(Json, 'json', api_ver=2)
