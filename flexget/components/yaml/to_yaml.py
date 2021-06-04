from loguru import logger
from yaml import dump as save_yaml, load as load_yaml

from flexget import plugin
from flexget.plugin import PluginError
from flexget.event import event
from flexget.entry import Entry
from flexget.utils import json, qualities
from flexget.task import EntryIterator, EntryContainer

PLUGIN_NAME = 'to_yaml'

logger = logger.bind(name=PLUGIN_NAME)

UPDATE_YAML = 'update'
REPLACE_YAML = 'replace'

DEFAULT_ACTION = UPDATE_YAML


class YamlOutput:
    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string'},
                    'fields': {'type': 'array', 'items': {'type': 'string'}},
                    'action': {
                        'type': 'string',
                        'enum': [REPLACE_YAML, UPDATE_YAML],
                        'default': DEFAULT_ACTION,
                    },
                },
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    def jsonify(self, data):
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
                    dic_list = self.jsonify(dict(lst))
                    new_list.append(dic_list)
                data[item] = new_list
            elif isinstance(data[item], Entry):
                data[item] = self.jsonify(dict(data[item]))
            elif isinstance(data[item], qualities.Quality):
                data[item] = str(data[item])
            elif isinstance(data[item], dict):
                data[item] = self.jsonify(data[item])
            else:
                try:
                    data[item] = json.dumps(data[item])
                    data[item] = json.loads(data[item])
                except TypeError:
                    del data[item]

        data.pop('_backlog_snapshot', None)

        return data

    def process_config(self, config: dict) -> dict:
        new_config = {}
        if isinstance(config, str):
            new_config['path'] = config
        else:
            new_config = config

        if 'fields' not in new_config:
            new_config['fields'] = []

        if 'action' not in new_config:
            new_config['action'] = DEFAULT_ACTION

        return new_config

    @plugin.internet(logger)
    def on_task_output(self, task, config):
        config = self.process_config(config)
        yaml_path = config['path']
        yaml_fields = config['fields']

        if config['action'] == UPDATE_YAML:
            try:
                yaml_file = open(config['path'])
            except FileNotFoundError as e:
                output_dict = {}
            except Exception as e:
                raise PluginError(f'Error opening yaml file `{yaml_path}`: {e}')
            else:
                try:
                    output_dict = load_yaml(yaml_file)
                except Exception as e:
                    raise PluginError(f'Error opening yaml file `{yaml_path}`: {e}')
        else:
            output_dict = {}

        for entry in task.accepted:
            entry_dict = self.jsonify(entry)

            title = entry_dict['title']

            for key, data in entry_dict.items():
                if key == 'title':
                    continue

                if yaml_fields and key not in yaml_fields:
                    continue

                if title not in output_dict:
                    output_dict[title] = {}

                output_dict[title][key] = data

        try:
            with open(yaml_path, 'w') as outfile:
                save_yaml(output_dict, outfile, default_flow_style=False)
        except Exception as e:
            raise PluginError(f'Error writhing data to `{yaml_path}`: {e}')


@event('plugin.register')
def register_plugin():
    plugin.register(YamlOutput, PLUGIN_NAME, api_ver=2)
