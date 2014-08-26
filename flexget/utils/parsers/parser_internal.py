from .parser_common import PARSER_EPISODE, PARSER_MOVIE
from .parser_common import Parser

from ..titles.movie import MovieParser
from ..titles.series import SeriesParser

import re


class InternalParser(Parser):
    def parse(self, input_, type_=None):
        internal_parser = None

        if type_ == PARSER_EPISODE:
            internal_parser = SeriesParser()
        elif type_ == PARSER_MOVIE:
            internal_parser = MovieParser()
        else:
            internal_parser = MovieParser()
        internal_parser.parse(input_)
        return internal_parser