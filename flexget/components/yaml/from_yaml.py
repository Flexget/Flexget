from unicodedata import normalize
import re

from loguru import logger

from flexget import plugin
from flexget.plugin import PluginError
from flexget.event import event
from flexget.entry import Entry

from yaml import load as load_yaml

PLUGIN_NAME = 'from_yaml'

logger = logger.bind(name=PLUGIN_NAME)


class YamlInput:
    schema = {
        'oneOf': [
            {'type': 'string', 'format': 'file'},
            {
                'type': 'object',
                'properties': {'path': {'type': 'string', 'format': 'file'}},
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    def simplify(self, text: str) -> str:
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

    def process_config(self, config: dict) -> dict:
        new_config = {}
        if isinstance(config, str):
            new_config['path'] = config
        else:
            new_config = config

        return new_config

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        config = self.process_config(config)

        yaml_path = config['path']

        try:
            yaml_file = open(config['path'])
        except FileNotFoundError as e:
            raise PluginError(f'Invalid file `{yaml_path}`: {e}')

        try:
            entries = load_yaml(yaml_file)
        except Exception as e:
            raise PluginError(f'Error opening yaml file `{yaml_path}`: {e}')

        if not isinstance(entries, dict):
            raise PluginError(f'List `{yaml_path}` must be a yaml with objects')

        for entry_title, entry_data in entries.items():
            entry = Entry()
            entry['title'] = entry_title
            entry.update(entry_data)
            if 'url' not in entry:
                entry['url'] = f'mock://{self.simplify(entry_title).replace(" ","_")}'
            yield entry


@event('plugin.register')
def register_plugin():
    plugin.register(YamlInput, PLUGIN_NAME, api_ver=2)
