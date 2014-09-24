from __future__ import unicode_literals, division, absolute_import

import logging
import re
import time
import types
from string import capwords

from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.titles.movie import MovieParser
from flexget.utils.titles.series import SeriesParser
from .parser_common import PARSER_EPISODE, PARSER_MOVIE, ParseWarning
from .parser_common import Parser, old_assume_quality


log = logging.getLogger('parser_internal')


def assume_quality_func(self, assumed_quality):
    self.quality = old_assume_quality(self.quality, assumed_quality)


class ParserInternal(Parser):
    def parse_serie(self, parser, input_):
        # We need to replace certain characters with spaces to make sure episode parsing works right
        # We don't remove anything, as the match positions should line up with the original title

        clean_title = re.sub('[_.,\[\]\(\):]', ' ', input_)
        if parser.parse_unwanted(clean_title):
            return False
        match = parser.parse_date(clean_title)
        if match:
            parser.identified_by = 'date'
        else:
            match = parser.parse_episode(clean_title)
            if match and parser.parse_unwanted(clean_title):
                return False
            parser.identified_by = 'ep'
        if not match:
            return False
        if match['match'].start() > 1:
            # We start using the original title here, so we can properly ignore unwanted prefixes.
            # Look for unwanted prefixes to find out where the series title starts
            start = 0
            prefix = re.match('|'.join(parser.ignore_prefixes), input_)
            if prefix:
                start = prefix.end()
            # If an episode id is found, assume everything before it is series name
            name = input_[start:match['match'].start()]
            # Remove possible episode title from series name (anything after a ' - ')
            name = name.split(' - ')[0]
            # Replace some special characters with spaces
            name = re.sub('[\._\(\) ]+', ' ', name).strip(' -')
            # Normalize capitalization to title case
            name = capwords(name)
            # If we didn't get a series name, return
            if not name:
                return
            parser.name = name
            parser.data = input_
            try:
                parser.parse(data=input_)
            except ParseWarning as pw:
                pass
            if parser.valid:
                return True

    def parse(self, data, type_=None, name=None, **kwargs):
        internal_parser = None

        if kwargs is None:
            kwargs = {}
        if name:
            kwargs['name'] = name

        metainfo = False
        try:
            metainfo = kwargs.pop('metainfo')
        except KeyError:
            pass

        if metainfo and type_ == PARSER_EPISODE:
            internal_parser = SeriesParser(**kwargs)
            internal_parser.assume_quality = types.MethodType(assume_quality_func, internal_parser)

            if self.parse_serie(internal_parser, data):
                return internal_parser
            else:
                type_ == PARSER_MOVIE

        if type_ == PARSER_EPISODE:
            internal_parser = SeriesParser(**kwargs)
        elif type_ == PARSER_MOVIE:
            internal_parser = MovieParser()
        else:
            internal_parser = MovieParser()
        internal_parser.assume_quality = types.MethodType(assume_quality_func, internal_parser)

        internal_parser.parse(data)

        return internal_parser

    #   movie_parser API
    @plugin.priority(1)
    def parse_movie(self, data, name=None, **kwargs):
        log.debug('Parsing movie: "' + data + '"' + ' (' + name + ')' if name else '' + ' [options:' + unicode(kwargs) + ']' if kwargs else '')
        start = time.clock()
        try:
            parsed = self.parse(data, PARSER_MOVIE, name=name, **kwargs)
        except ParseWarning as pw:
            log_once(pw.value, logger=log)
            parsed = pw.parsed
        end = time.clock()
        log.debug('Parsing result: ' + unicode(parsed) + ' (in ' + unicode((end - start) * 1e3) + ' ms)')
        return parsed

    #   series_parser API
    @plugin.priority(1)
    def parse_series(self, data, name=None, **kwargs):
        log.debug('Parsing series: "' + data + '"' + ' (' + name + ')' if name else '' + ' [options:' + unicode(kwargs) + ']' if kwargs else '')
        start = time.clock()
        try:
            parsed = self.parse(data, PARSER_EPISODE, name=name, **kwargs)
        except ParseWarning as pw:
            log_once(pw.value, logger=log)
            parsed = pw.parsed
        end = time.clock()
        log.debug('Parsing result: ' + unicode(parsed) + ' (in ' + unicode((end - start) * 1e3) + ' ms)')
        return parsed


@event('plugin.register')
def register_plugin():
    plugin.register(ParserInternal, 'parser_internal',
                    groups=['movie_parser', 'series_parser'],
                    api_ver=2
    )
