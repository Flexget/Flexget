from .parser_common import PARSER_EPISODE, PARSER_MOVIE, PARSER_VIDEO
from .parser_common import ParsedEntry, ParsedVideoQuality, ParsedVideo, ParsedSerie, ParsedMovie, Parser

from ..titles.movie import MovieParser
from ..titles.series import SeriesParser


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