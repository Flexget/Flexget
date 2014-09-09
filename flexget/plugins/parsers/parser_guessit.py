from __future__ import unicode_literals, division, absolute_import

import logging

from flexget import plugin
from flexget.event import event

from flexget.utils.parsers import PARSER_MOVIE, PARSER_EPISODE
from flexget.utils.parsers.parser_guessit import GuessitParser

log = logging.getLogger('parser_guessit')


class ParserGuessit(object):
    def __init__(self):
        self.parser = GuessitParser()

    #   movie_parser API
    def parse_movie(self, data, name=None, **kwargs):
        return self.parser.parse(data, PARSER_MOVIE, name=name, **kwargs)

    #   series_parser API
    def parse_series(self, data, name=None, **kwargs):
        return self.parser.parse(data, PARSER_EPISODE, name=name, **kwargs)

@event('plugin.register')
def register_plugin():
    plugin.register(ParserGuessit, 'parser_guessit',
                    groups=['movie_parser', 'series_parser'],
                    api_ver=2, priority=100
    )
