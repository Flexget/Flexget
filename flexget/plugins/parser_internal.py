from __future__ import unicode_literals, division, absolute_import

import logging

from flexget import plugin
from flexget.event import event

from flexget.utils.parsers import PARSER_MOVIE, PARSER_EPISODE
from flexget.utils.parsers.parser_common import ParseWarning
from flexget.utils.parsers.parser_internal import InternalParser

log = logging.getLogger('parser_internal')


class ParserInternal(object):
    def __init__(self):
        self.parser = InternalParser()

    #   movie_parser API
    def parse_movie(self, data, name=None, **kwargs):
        try:
            return self.parser.parse(data, PARSER_MOVIE, name=name, **kwargs)
        except ParseWarning as e:
            log.warn(e)
            return e.parsed

    #   series_parser API
    def parse_series(self, data, name=None, **kwargs):
        try:
            return self.parser.parse(data, PARSER_EPISODE, name=name, **kwargs)
        except ParseWarning as e:
            log.warn(e)
            return e.parsed

@event('plugin.register')
def register_plugin():
    plugin.register(ParserInternal, 'parser_internal',
                    groups=['movie_parser', 'series_parser'],
                    api_ver=2
    )
