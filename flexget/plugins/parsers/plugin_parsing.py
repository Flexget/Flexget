from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('parsing')
PARSER_TYPES = ['movie', 'series']


class PluginParsing(object):
    """
    Provides parsing framework
    """

    def __init__(self):
        self.parsers = {}
        self.parses_names = {}
        self.default_parser = {}
        for parser_type in PARSER_TYPES:
            self.parsers[parser_type] = {}
            self.parses_names[parser_type] = {}
            for p in plugin.get_plugins(group=parser_type + '_parser'):
                self.parsers[parser_type][p.name.replace('parser_', '')] = p.instance
                self.parses_names[parser_type][p.name.replace('parser_', '')] = p.name
            # Select default parsers based on priority
            func_name = 'parse_' + parser_type
            self.default_parser[parser_type] = max(self.parsers[parser_type].values(),
                                                   key=lambda p: getattr(getattr(p, func_name), 'priority', 0))
        self.parser = self.default_parser

    @property
    def schema(self):
        # Create a schema allowing only our registered parsers to be used under the key of each parser type
        properties = dict((parser_type, {'type': 'string', 'enum': self.parses_names[parser_type].keys()})
                          for parser_type in self.parses_names)
        s = {
            'type': 'object',
            'properties': properties,
            'additionalProperties': False
        }
        return s

    def on_task_start(self, task, config):
        if not config:
            return
        # Set up user selected parsers from config for this task run
        self.parser = self.default_parser.copy()
        for parser_type, parser_name in config.iteritems():
            self.parser[parser_type] = plugin.get_plugin_by_name('parser_' + parser_name).instance

    def on_task_end(self, task, config):
        # Restore default parsers for next task run
        self.parser = self.default_parser

    on_task_abort = on_task_end

    def parse_series(self, data, name=None, **kwargs):
        """
        Use the selected series parser to parse series information from `data`

        :param data: The raw string to parse information from.
        :param name: The series name to parse data for. If not supplied, parser will attempt to guess series name
            automatically from `data`.

        :returns: An object containing the parsed information. The `valid` attribute will be set depending on success.
        """
        return self.parser['series'].parse_series(data, name=name, **kwargs)

    def parse_movie(self, data, **kwargs):
        """
        Use the selected movie parser to parse movie information from `data`

        :param data: The raw string to parse information from

        :returns: An object containing the parsed information. The `valid` attribute will be set depending on success.
        """
        return self.parser['movie'].parse_movie(data, **kwargs)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginParsing, 'parsing', api_ver=2)
