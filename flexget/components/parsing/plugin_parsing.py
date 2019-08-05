from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('parsing')
PARSER_TYPES = ['movie', 'series']

# Mapping of parser type to (mapping of parser name to plugin instance)
parsers = {}
# Mapping from parser type to the name of the default/selected parser for that type
default_parsers = {}
selected_parsers = {}


# We need to wait until manager startup to access other plugin instances, to make sure they have all been loaded
@event('manager.startup')
def init_parsers(manager):
    """Prepare our list of parsing plugins and default parsers."""
    for parser_type in PARSER_TYPES:
        parsers[parser_type] = {}
        for p in plugin.get_plugins(interface=parser_type + '_parser'):
            parsers[parser_type][p.name.replace('parser_', '')] = p.instance
        # Select default parsers based on priority
        func_name = 'parse_' + parser_type
        default_parsers[parser_type] = max(
            iter(parsers[parser_type].items()),
            key=lambda p: getattr(getattr(p[1], func_name), 'priority', 0),
        )[0]
        log.debug(
            'setting default %s parser to %s. (options: %s)'
            % (parser_type, default_parsers[parser_type], parsers[parser_type])
        )


class PluginParsing(object):
    """Provides parsing framework"""

    @property
    def schema(self):
        # Create a schema allowing only our registered parsers to be used under the key of each parser type
        properties = {}
        for parser_type in PARSER_TYPES:
            parser_names = [
                p.name.replace('parser_', '')
                for p in plugin.get_plugins(interface=parser_type + '_parser')
            ]
            properties[parser_type] = {'type': 'string', 'enum': parser_names}
        s = {'type': 'object', 'properties': properties, 'additionalProperties': False}
        return s

    def on_task_start(self, task, config):
        # Set up user selected parsers from config for this task run
        if config:
            selected_parsers.update(config)

    def on_task_exit(self, task, config):
        # Restore default parsers for next task run
        selected_parsers.clear()

    on_task_abort = on_task_exit

    def parse_series(self, data, name=None, **kwargs):
        """
        Use the selected series parser to parse series information from `data`

        :param data: The raw string to parse information from.
        :param name: The series name to parse data for. If not supplied, parser will attempt to guess series name
            automatically from `data`.

        :returns: An object containing the parsed information. The `valid` attribute will be set depending on success.
        """
        parser = parsers['series'][selected_parsers.get('series', default_parsers.get('series'))]
        return parser.parse_series(data, name=name, **kwargs)

    def parse_movie(self, data, **kwargs):
        """
        Use the selected movie parser to parse movie information from `data`

        :param data: The raw string to parse information from

        :returns: An object containing the parsed information. The `valid` attribute will be set depending on success.
        """
        parser = parsers['movie'][selected_parsers.get('movie') or default_parsers['movie']]
        return parser.parse_movie(data, **kwargs)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginParsing, 'parsing', api_ver=2)
