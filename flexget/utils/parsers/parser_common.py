from .. import qualities

from abc import abstractproperty, abstractmethod, ABCMeta

PARSER_ANY = 0
PARSER_VIDEO = 1
PARSER_MOVIE = 2
PARSER_EPISODE = 3

_default_parser = 'flexget.utils.parsers.parser_guessit.GuessitParser'
_parsers = {}


def _get_class(kls):
    parts = kls.split('.')
    if len(parts) <= 1:
        return None

    module = ".".join(parts[:-1])
    m = __import__(module)
    for comp in parts[1:]:
        m = getattr(m, comp)

    return m


def set_default_parser(parser_name):
    global _default_parser
    _default_parser = parser_name


def get_parser(parser_name=None):
    global _default_parser
    parser_name = parser_name or _default_parser
    parser = _parsers.get(parser_name)
    if not parser:
        parser_class = _get_class(parser_name)
        if not parser_class:
            parser_class = _get_class('flexget.utils.parsers.' + parser_name)
        parser = parser_class()
    return parser


class ParsedEntry(ABCMeta(str('ParsedEntryABCMeta'), (object,), {})):
    """
    A parsed entry, containing parsed data like name, year, episodeNumber and season.
    """

    def __init__(self, raw):
        self._raw = raw

    @property
    def raw(self):
        return self._raw

    @property
    def data(self):
        return self.raw

    @abstractproperty
    def name(self):
        raise NotImplementedError

    @abstractproperty
    def valid(self):
        raise NotImplementedError

    @abstractproperty
    def proper(self):
        raise NotImplementedError

    @property
    def proper_count(self):
        # todo: deprecated. We should remove this field from the rest of code.
        return 1 if self.proper else 0

    @abstractproperty
    def date(self):
        raise NotImplementedError

    @abstractproperty
    def release_group(self):
        raise NotImplementedError

    @abstractproperty
    def properties(self):
        raise NotImplementedError

    def __str__(self):
        return "<%s(name=%s)>" % (self.__class__.__name__, self.name)


class ParsedVideo(ABCMeta(str('ParsedVideoABCMeta'), (ParsedEntry,), {})):
    _old_quality = None

    @abstractproperty
    def year(self):
        raise NotImplementedError

    @abstractproperty
    def subtitle_languages(self):
        raise NotImplementedError

    @abstractproperty
    def languages(self):
        raise NotImplementedError

    @abstractproperty
    def quality2(self):
        raise NotImplementedError

    @abstractproperty
    def is_3d(self):
        raise NotImplementedError

    @property
    def quality(self):
        # todo: deprecated. We should remove this field from the rest of code.
        if not self._old_quality:
            self._old_quality = self.quality2.to_old_quality()
        return self._old_quality

    def __str__(self):
        return "<%s(name=%s,year=%s)>" % (self.__class__.__name__, self.name, self.year)


class ParsedVideoQuality(ABCMeta(str('ParsedVideoQualityABCMeta'), (object,), {})):
    @abstractproperty
    def screen_size(self):
        raise NotImplementedError

    @abstractproperty
    def source(self):
        raise NotImplementedError

    @abstractproperty
    def format(self):
        raise NotImplementedError

    @abstractproperty
    def video_codec(self):
        raise NotImplementedError

    @abstractproperty
    def video_profile(self):
        raise NotImplementedError

    @abstractproperty
    def audio_codec(self):
        raise NotImplementedError

    @abstractproperty
    def audio_profile(self):
        raise NotImplementedError

    @abstractproperty
    def audio_channels(self):
        raise NotImplementedError

    @abstractproperty
    def is_screener(self):
        raise NotImplementedError

    def to_old_quality(self):
        resolution = self.screen_size
        source = self.format.replace('-', '') if self.format else None
        codec = self.video_codec
        audio = self.audio_codec + (self.audio_channels if self.audio_channels else '') if self.audio_codec else None

        return qualities.Quality(' '.join(filter(None, [resolution, source, codec, audio])))

    def __str__(self):
        return "<%s(screen_size=%s,source=%s,video_codec=%s,audio_channels=%s)>" % (
        self.__class__.__name__, self.screen_size, self.source, self.video_codec, self.audio_channels)


class ParsedMovie(ABCMeta(str('ParsedMovieABCMeta'), (ParsedVideo,), {})):
    @abstractproperty
    def title(self):
        raise NotImplementedError


class ParsedSerie(ABCMeta(str('ParsedSerieABCMeta'), (ParsedVideo,), {})):
    @abstractproperty
    def serie(self):
        raise NotImplementedError

    @abstractproperty
    def title(self):
        raise NotImplementedError

    @abstractproperty
    def season(self):
        raise NotImplementedError

    @abstractproperty
    def episode(self):
        raise NotImplementedError

    @abstractproperty
    def episode_list(self):
        raise NotImplementedError

    @abstractproperty
    def episode_details(self):
        raise NotImplementedError

    def __str__(self):
        return "<%s(name=%s,season=%s,episode=%s)>" % (self.__class__.__name__, self.name, self.season,
                                                       self.episodes if self.episodes and len(
                                                           self.episodes) > 1 else self.episode)


class Parser(ABCMeta(str('ParserABCMeta'), (object,), {})):
    @abstractmethod
    def parse(self, input_, type_=None):
        """

        :param input_: string to parse
        :param type_: a PARSER_* type
        :return: an instance of :class:`ParsedEntry`
        """
        raise NotImplementedError

