from .parser_common import PARSER_EPISODE, PARSER_MOVIE
from .parser_common import Parser, old_assume_quality

from ..titles.movie import MovieParser
from ..titles.series import SeriesParser

import types
import re


def assume_quality_func(self, assumed_quality):
    self.quality = old_assume_quality(self.quality, assumed_quality)


class InternalParser(Parser):
    def parse(self, input_, type_=None, attended_name=None, **kwargs):
        internal_parser = None

        if type_ == PARSER_EPISODE:
            if kwargs is None:
                kwargs = {}
            if attended_name:
                kwargs['name'] = attended_name
            internal_parser = SeriesParser(**kwargs)
        elif type_ == PARSER_MOVIE:
            internal_parser = MovieParser()
        else:
            internal_parser = MovieParser()
        internal_parser.assume_quality = types.MethodType(assume_quality_func, internal_parser)

        internal_parser.parse(input_)

        return internal_parser