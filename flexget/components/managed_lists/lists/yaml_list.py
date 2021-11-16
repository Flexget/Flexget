import random
from collections.abc import MutableSet
from typing import Optional

from loguru import logger
from yaml import dump as dump_yaml
from yaml import safe_load as load_yaml

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils import json

PLUGIN_NAME = 'yaml_list'

logger = logger.bind(name=PLUGIN_NAME)


class YamlManagedList(MutableSet):
    def __init__(self, path: str, fields: list, key: str, encoding: str):
        self.filename = path
        self.fields = fields
        self.ecoding = encoding
        self.key = key
        self.entries = []
        try:
            content = open(self.filename)
        except FileNotFoundError as exc:
            entries = []
            pass
        else:
            try:
                # TODO: use the load from our serialization system if that goes in
                entries = load_yaml(content)
            except Exception as exc:
                raise PluginError(f'Error opening yaml file `{self.filename}`: {exc}')
        if not entries:
            return
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    entry = Entry(**entry)
                else:
                    raise PluginError(f'Elements of `{self.filename}` must be dictionaries')
                if not entry.get('url'):
                    entry['url'] = f'mock://localhost/entry_list/{random.random()}'
                self.entries.append(entry)
        else:
            raise PluginError(f'List `{self.filename}` must be a yaml list')

    def filter_keys(self, item: dict) -> dict:
        """Gets items with limited keys

        Args:
            item (dict): item to return

        Returns:
            dict: Item with limited keys
        """


        # Title should allways be the first item
        if self.key != 'title':
            required_fields = [self.key]

        required_fields.append('title')

        if not self.fields:
            fields = [k for k in item if not k.startswith('_') and k not in required_fields]
        else:
            fields = [k for k in item if k in self.fields and k not in required_fields]

        fields.sort()

        for field in required_fields:
            fields.insert(0, field)

        if not self.fields:
            return {k: item[k] for k in fields if not k.startswith('_')}
        return {k: item[k] for k in fields if k in self.fields or k in required_fields}

    def matches(self, entry1, entry2) -> bool:
        return entry1[self.key] == entry2[self.key]

    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)

    def __contains__(self, item):
        return bool(self.get(item))

    def save_yaml(self):
        """Saves yaml

        Raises:
            PluginError: Error
        """

        out = []
        for entry in self.entries:
            out.append(json.coerce(self.filter_keys(entry)))

        try:
            with open(self.filename, 'w') as outfile:
                dump_yaml(
                    out,
                    outfile,
                    default_flow_style=False,
                    encoding=self.ecoding,
                    allow_unicode=True,
                    sort_keys=False,
                )
        except Exception as e:
            raise PluginError(f'Error writhing data to `{self.filename}`: {e}')

    def get(self, item) -> Optional[Entry]:
        for entry in self.entries:
            if self.matches(item, entry):
                return entry
        return None

    def add(self, entry: Entry) -> None:
        exists = self.get(entry)
        if exists:
            logger.warning(
                f'Can\'t add entry "{self.key}" = "{exists.get(self.key)}", entry already exists in list'
            )
            return
        self.entries.append(entry)
        self.save_yaml()

    def discard(self, item) -> None:
        key = item.get(self.key, None)
        if not key:
            logger.error(f'Can\'t add entry, no `{key}` field')
            return

        for i, entry in enumerate(self.entries):
            if self.matches(item, entry):
                self.entries.pop(i)
                break
        else:
            return

        self.save_yaml()

    @property
    def online(self):
        return False

    @property
    def immutable(self):
        return False


class YamlList:
    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string'},
                    'fields': {'type': 'array', 'items': {'type': 'string'}},
                    'encoding': {'type': 'string', 'default': 'utf-8'},
                    'key': {'type': 'string', 'default': 'title'},
                },
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    def process_config(self, config: dict) -> dict:
        if isinstance(config, str):
            config = {'path': config}
        config.setdefault('fields', [])
        config.setdefault('encoding', 'utf-8')
        config.setdefault('key', 'title')
        return config

    def get_list(self, config):
        config = self.process_config(config)
        return YamlManagedList(**config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        config = self.process_config(config)
        yaml_list = YamlManagedList(**config)
        for item in yaml_list:
            yield item


@event('plugin.register')
def register_plugin():
    plugin.register(YamlList, PLUGIN_NAME, api_ver=2, interfaces=['task', 'list'])
