from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('parsing')


class PluginParsing(object):
    """
    Provides parsing framework
    """
    schema = {
        'type': 'object',
        'properties': {
            'movie_parser': {'type': 'string'},
            'series_parser': {'type': 'string'}

        },
        'additionalProperties': False
    }

    movie_parser = None
    series_parser = None

    def on_task_start(self, task, config):
        movie_parser_plugin = plugin.get_plugin(group='movie_parser', name=config.get('movie_parser') if config else None)
        if not movie_parser_plugin and config and config.get('movie_parser'):
            log.warn("Invalid value %s for movie_parser. Using default ..." % (config.get('movie_parser')))
            movie_parser_plugin = plugin.get_plugin(group='movie_parser')
        self.movie_parser = movie_parser_plugin.instance
        if config and config.get('movie_parser'):
            log.verbose("Using %s as movie parser." % (movie_parser_plugin.name,))

        series_parser_plugin = plugin.get_plugin(group='series_parser', name=config.get('series_parser') if config else None)
        if not series_parser_plugin and config and config.get('series_parser'):
            log.warn("Invalid value %s for series_parser. Using default ..." % (config.get('series_parser')))
            series_parser_plugin = plugin.get_plugin(group='series_parser')
        self.series_parser = series_parser_plugin.instance
        if config and config.get('series_parser'):
            log.verbose("Using %s as series parser." % (series_parser_plugin.name,))

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