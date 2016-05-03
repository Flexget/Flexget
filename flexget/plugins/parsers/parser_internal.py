from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import time

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.titles.movie import MovieParser
from flexget.utils.titles.series import SeriesParser
from .parser_common import ParseWarning


log = logging.getLogger('parser_internal')


class ParserInternal(object):
    # movie_parser API
    @plugin.priority(1)
    def parse_movie(self, data, **kwargs):
        log.debug('Parsing movie: `%s` kwargs: %s', data, kwargs)
        start = time.clock()
        parser = MovieParser()
        try:
            parser.parse(data)
        except ParseWarning as pw:
            log_once(pw.value, logger=log)
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parser, (end - start) * 1000)
        return parser

    # series_parser API
    @plugin.priority(1)
    def parse_series(self, data, **kwargs):
        log.debug('Parsing series: `%s` kwargs: %s', data, kwargs)
        start = time.clock()
        parser = SeriesParser(**kwargs)
        try:
            parser.parse(data)
        except ParseWarning as pw:
            log_once(pw.value, logger=log)
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parser, (end - start) * 1000)
        return parser


@event('plugin.register')
def register_plugin():
    plugin.register(ParserInternal, 'parser_internal', groups=['movie_parser', 'series_parser'], api_ver=2)
