from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import time

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.titles.movie import MovieParser
from flexget.utils.titles.series import SeriesParser
from .parser_common import ParseWarning, MovieParseResult, SeriesParseResult

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
        result = MovieParseResult(
            data=data,
            name=parser.name,
            year=parser.year,
            quality=parser.quality,
            proper_count=parser.proper_count
        )
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parser, (end - start) * 1000)
        return result

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
        # TODO: Returning this invalid object seems a bit silly, raise an exception is probably better
        if not parser.valid:
            return SeriesParseResult(valid=False)
        result = SeriesParseResult(
            data=data,
            name=parser.name,
            episodes=parser.episodes,
            id=parser.id,
            id_type=parser.id_type,
            quality=parser.quality,
            proper_count=parser.proper_count,
            special=parser.special,
            group=parser.group,
            season_pack=parser.season_pack,
            strict_name=parser.strict_name,
            identified_by=parser.identified_by
        )
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parser, (end - start) * 1000)
        return result


@event('plugin.register')
def register_plugin():
    plugin.register(ParserInternal, 'parser_internal', interfaces=['movie_parser', 'series_parser'], api_ver=2)
