from unicodedata import normalize
from collections.abc import MutableSet
import re

from loguru import logger
from yaml import dump as save_yaml, load as load_yaml

from flexget import plugin
from flexget.plugin import PluginError
from flexget.event import event
from flexget.entry import Entry
from flexget.utils import json, qualities
from flexget.task import EntryIterator, EntryContainer

PLUGIN_NAME = 'yaml_list'

logger = logger.bind(name=PLUGIN_NAME)


def jsonify(data):
    """
    Ensures that data is JSON friendly
    """

    if isinstance(data, str):
        return data

    try:
        _ = (e for e in data)
    except TypeError:
        return data

    for item in data:
        if isinstance(data[item], (EntryIterator, EntryContainer)):
            lists = list(data[item])
            new_list = []
            for lst in lists:
                dic_list = jsonify(dict(lst))
                new_list.append(dic_list)
            data[item] = new_list
        elif isinstance(data[item], Entry):
            data[item] = jsonify(dict(data[item]))
        elif isinstance(data[item], qualities.Quality):
            data[item] = str(data[item])
        elif isinstance(data[item], dict):
            data[item] = jsonify(data[item])
        else:
            try:
                data[item] = json.dumps(data[item])
                data[item] = json.loads(data[item])
            except TypeError:
                del data[item]

    data.pop('_backlog_snapshot', None)

    return data


def simplify(text: str) -> str:
    """ Siplify text """

    if not isinstance(text, str):
        return text

    # Replace accented chars by their 'normal' couterparts
    result = normalize('NFKD', text)

    # Symbols that should be converted to white space
    result = re.sub(r'[ \(\)\-_\[\]\.]+', ' ', result)
    # Leftovers
    result = re.sub(r"[^a-zA-Z0-9 ]", "", result)
    # Replace multiple white spaces with one
    result = ' '.join(result.split())

    return result


class YamlManagedList(MutableSet):
    _yaml_file = None
    _yaml_fields = []
    _yaml_items = {}

    def __init__(self, path: str, fields, *args, **kwargs):
        self._yaml_file = path

        if isinstance(fields, list):
            self._yaml_fields = fields

        try:
            content = open(self._yaml_file)
        except FileNotFoundError as e:
            output_dict = {}
        else:
            try:
                output_dict = load_yaml(content)
            except Exception as e:
                raise PluginError(f'Error opening yaml file `{self._yaml_file}`: {e}')

        if isinstance(output_dict, dict):
            self._yaml_items = output_dict
        else:
            raise PluginError(f'List `{self._yaml_file}` must be a yaml with objects')

    def _output_item(self, title: str, item: dict) -> dict:
        """Returns item in output format

        Args:
            title (str): entry name
            item (dict): entry data

        Returns:
            [dict]: Output formated item
        """

        if not item:
            return None

        item = self._get_item_fields(item)
        output_item = {}
        output_item['title'] = title
        output_item.update(item)

        if 'url' not in output_item:
            output_item['url'] = f'mock://{simplify(title).replace(" ","_")}'

        return output_item

    def _get_item_fields(self, item: dict) -> dict:
        """Gets items with limited keys

        Args:
            item (dict): item to return

        Returns:
            dict: Item with limited keys
        """

        output_items = {}
        for key, data in item.items():
            if key == 'title':
                continue

            if self._yaml_fields and key not in self._yaml_fields:
                continue

            output_items[key] = jsonify(data)

        return output_items

    def __iter__(self):
        new_list = []
        for key, data in self._yaml_items.items():
            new_list.append(self._output_item(key, data))

        return iter(new_list)

    def __len__(self):
        return len(self._yaml_items.keys())

    def __contains__(self, item):
        return bool(self.get(item))

    def save_yaml(self):
        """Saves yaml

        Raises:
            PluginError: Error
        """

        try:
            with open(self._yaml_file, 'w') as outfile:
                save_yaml(self._yaml_items, outfile, default_flow_style=False)
        except Exception as e:
            raise PluginError(f'Error writhing data to `{self._yaml_file}`: {e}')

    def get(self, item) -> None:
        title = item.get('title', None)
        if not title:
            logger.error('Can\'t get entry, no `title` field')
            return

        item = next((data for key, data in self._yaml_items.items() if key == title), None)
        if not item:
            return None

        item = self._output_item(title, item)
        return item

    def add(self, item) -> None:
        title = item.get('title', None)
        if not title:
            logger.error('Can\'t add entry, no `title` field')
            return

        if isinstance(item, Entry):
            new_item_dict = {}
            for key, data in item.items():
                new_item_dict[key] = data
            item = new_item_dict

        item_dict = self._get_item_fields(item)
        item_dict = {title: jsonify(item_dict)}
        item_dict.pop('title', None)
        self._yaml_items.update(item_dict)
        self.save_yaml()

    def discard(self, item) -> None:
        title = item.get('title', None)
        if not title:
            logger.error('Can\'t add entry, no `title` field')
            return

        self._yaml_items.pop(title, None)
        self.save_yaml()

    @property
    def online(self):
        return True

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
                },
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    def process_config(self, config: dict) -> dict:
        """Process config

        Args:
            config (dict): Config to process

        Returns:
            dict: Processed config
        """

        new_config = {}
        if isinstance(config, str):
            new_config['path'] = config
        else:
            new_config = config

        if 'fields' not in new_config:
            new_config['fields'] = []

        return new_config

    def item_to_entry(self, item: dict) -> Entry:
        """Get's entry from item

        Args:
            item (dict): Item to return as entry

        Returns:
            Entry: Entry
        """

        if not item:
            return None
        new_entry = Entry()
        new_entry.update(item)
        return new_entry

    def get_list(self, config):
        config = self.process_config(config)
        return YamlManagedList(**config)

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        config = self.process_config(config)
        yaml_list = YamlManagedList(**config)
        for item in yaml_list:
            yield self.item_to_entry(item)


@event('plugin.register')
def register_plugin():
    plugin.register(YamlList, PLUGIN_NAME, api_ver=2, interfaces=['task', 'list'])
