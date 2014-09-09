from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('parsing')


class PluginParsing(object):
    """
    Provides parsing framework
    """
    _default = 'guessit'

    schema = {
        'type': 'object',
        'properties': {
            'movie_parser': {'type': 'string', 'default': _default},
            'series_parser': {'type': 'string', 'default': _default}

        },
        'additionalProperties': False
    }

    movie_parser = None
    series_parser = None

    def on_task_start(self, task, config):
        if config:
            if 'movie_parser' in config:
                for movie_parser_plugin in plugin.get_plugins(group='movie_parser'):
                    if movie_parser_plugin.name in [config['movie_parser'], 'parser_' + config['movie_parser']]:
                        self.movie_parser = movie_parser_plugin.instance
                        log.verbose("Using %s as movie parser." % (movie_parser_plugin.name,))
                        break
            if 'series_parser' in config:
                for series_parser_plugin in plugin.get_plugins(group='series_parser'):
                    if series_parser_plugin.name in [config['series_parser'], 'parser_' + config['series_parser']]:
                        self.series_parser = series_parser_plugin.instance
                        log.verbose("Using %s as series parser." % (movie_parser_plugin.name,))
                        break

        if not self.movie_parser:
            self.movie_parser = plugin.get_plugin_by_name(self._default if self._default.startswith('parser_') else 'parser_' + self._default).instance

        if not self.series_parser:
            self.series_parser = plugin.get_plugin_by_name(self._default if self._default.startswith('parser_') else 'parser_' + self._default).instance

    def on_task_end(self, task, config):
        self.movie_parser = None
        self.series_parser = None

    #   movie_parser API
    def parse_movie(self, data, name=None, **kwargs):
        return self.movie_parser.parse_movie(data, name=name, **kwargs)

    #   series_parser API
    def parse_series(self, data, name=None, **kwargs):
        return self.series_parser.parse_series(data, name=name, **kwargs)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginParsing, 'parsing', builtin=True, api_ver=2)