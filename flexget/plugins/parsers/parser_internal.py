from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import time

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.titles.movie import MovieParser
from flexget.utils.titles.series import SeriesParser
from .parser_common import ParseWarning

log = logging.getLogger('parser_internal')

series_parser_cache = lru_cache()(SeriesParser)


def series_parser_factory(**kwargs):
    """Returns a series parser from the cache, or creates one."""
    if not kwargs.get('name'):
        # Don't cache parsing calls that aren't for a specific series (e.g. from metainfo_series or series_premiere)
        return SeriesParser(**kwargs)
    # Turn our list arguments to tuples so that they are hashable by lru_cache
    for key, val in kwargs.items():
        if isinstance(val, list):
            kwargs[key] = tuple(val)
    return series_parser_cache(**kwargs)


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
        parser = series_parser_factory(**kwargs)
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
