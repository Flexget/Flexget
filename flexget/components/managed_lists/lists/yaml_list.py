import random
import typing
from collections import OrderedDict
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
    def __init__(self, path: str, fields: list, encoding: str):
        self.filename = path
        self.fields = fields
        self.encoding = encoding

        self.entries = []
        try:
            content = open(self.filename, encoding=self.encoding)
        except FileNotFoundError:
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

    def filter_keys(self, item: typing.Mapping) -> dict:
        """Gets items with limited keys

        Args:
            item (dict): item to return

        Returns:
            dict: Item with limited keys
        """
        required_fields = ['title']
        if not self.fields:
            return {k: item[k] for k in item if not k.startswith('_')}
        return {k: item[k] for k in item if k in self.fields or k in required_fields}

    def matches(self, entry1, entry2) -> bool:
        return entry1['title'] == entry2['title']

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
        top_fields = ['title', 'url']

        def sort_key(item: typing.Tuple[str, typing.Any]) -> typing.Tuple[int, str]:
            # Sort important fields first, then the rest of the fields alphabetically
            try:
                return top_fields.index(item[0]), ''
            except ValueError:
                return len(top_fields), item[0]

        out = []
        for entry in self.entries:
            filtered_entry = json.coerce(self.filter_keys(entry))
            out.append(OrderedDict(sorted(filtered_entry.items(), key=sort_key)))

        try:
            # By default we try to write strings natively to the file, for nicer manual reading/writing
            out_bytes = dump_yaml(
                out, default_flow_style=False, encoding=self.encoding, allow_unicode=True
            )
        except UnicodeEncodeError:
            # If strings are not representable in the specified file encoding, let yaml use backslash escapes
            out_bytes = dump_yaml(out, default_flow_style=False, encoding=self.encoding)

        try:
            with open(self.filename, 'wb') as outfile:
                outfile.write(out_bytes)
        except Exception as e:
            raise PluginError(f'Error writhing data to `{self.filename}`: {e}')

    def get(self, item) -> Optional[Entry]:
        for entry in self.entries:
            if self.matches(item, entry):
                return entry
        return None

    def add(self, item: Entry) -> None:
        for i, entry in enumerate(self.entries):
            if self.matches(item, entry):
                self.entries[i] = item
                break
        else:
            self.entries.append(item)

        self.save_yaml()

    def discard(self, item) -> None:
        title = item.get('title', None)
        if not title:
            logger.error('Can\'t add entry, no `title` field')
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
        return config

    def get_list(self, config):
        config = self.process_config(config)
        return YamlManagedList(**config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        config = self.process_config(config)
        yaml_list = YamlManagedList(**config)
        yield from yaml_list


@event('plugin.register')
def register_plugin():
    plugin.register(YamlList, PLUGIN_NAME, api_ver=2, interfaces=['task', 'list'])
