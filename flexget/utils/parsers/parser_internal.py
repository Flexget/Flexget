from flexget.utils.parsers.parser_common import PARSER_ANY
from .parser_common import PARSER_EPISODE, PARSER_MOVIE, ParseWarning
from .parser_common import Parser, old_assume_quality

from ..titles.movie import MovieParser
from ..titles.series import SeriesParser

from string import capwords

import types
import re


def assume_quality_func(self, assumed_quality):
    self.quality = old_assume_quality(self.quality, assumed_quality)


class InternalParser(Parser):
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

        if not type_ or type_ == PARSER_ANY:
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