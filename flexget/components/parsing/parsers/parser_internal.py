import time

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.parsers.generic import ParseWarning
from flexget.utils.parsers.movie import MovieParser
from flexget.utils.parsers.series import SeriesParser

from .parser_common import MovieParseResult, SeriesParseResult

logger = logger.bind(name='parser_internal')


try:
    preferred_clock = time.process_time
except AttributeError:
    preferred_clock = time.clock


class ParserInternal:

    # movie_parser API

    @plugin.priority(1)
    def parse_movie(self, data, **kwargs):
        logger.debug('Parsing movie: `{}` kwargs: {}', data, kwargs)
        start = preferred_clock()
        parser = MovieParser()
        try:
            parser.parse(data)
        except ParseWarning as pw:
            log_once(pw.value, logger=logger)
        result = MovieParseResult(
            data=data,
            name=parser.name,
            year=parser.year,
            quality=parser.quality,
            proper_count=parser.proper_count,
            valid=bool(parser.name),
        )
        logger.debug('Parsing result: {} (in {} ms)', parser, (preferred_clock() - start) * 1000)
        return result

    # series_parser API
    @plugin.priority(1)
    def parse_series(self, data, **kwargs):
        logger.debug('Parsing series: `{}` kwargs: {}', data, kwargs)
        start = preferred_clock()
        parser = SeriesParser(**kwargs)
        try:
            parser.parse(data)
        except ParseWarning as pw:
            log_once(pw.value, logger=logger)
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
            identified_by=parser.identified_by,
        )
        logger.debug('Parsing result: {} (in {} ms)', parser, (preferred_clock() - start) * 1000)
        return result


@event('plugin.register')
def register_plugin():
    plugin.register(
        ParserInternal, 'parser_internal', interfaces=['movie_parser', 'series_parser'], api_ver=2
    )
