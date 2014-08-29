from .. import qualities

from abc import abstractproperty, abstractmethod, ABCMeta
from string import capwords

from flexget.utils.tools import ReList

import re
import logging

log = logging.getLogger('parser')

PARSER_ANY = 0
PARSER_VIDEO = 1
PARSER_MOVIE = 2
PARSER_EPISODE = 3

_default_parser = 'flexget.utils.parsers.parser_guessit.GuessitParser'
#_default_parser = 'flexget.utils.parsers.parser_internal.InternalParser'
_parsers = {}

SERIES_ID_TYPES = ['ep', 'date', 'sequence', 'id']

def clean_value(name):
    # Move anything in leading brackets to the end
    #name = re.sub(r'^\[(.*?)\](.*)', r'\2 \1', name)

    for char in '[]()_,.':
        name = name.replace(char, ' ')

    # if there are no spaces
    if name.find(' ') == -1:
        name = name.replace('-', ' ')

    # remove unwanted words (imax, ..)
    #self.remove_words(data, self.remove)

    #MovieParser.strip_spaces
    name = ' '.join(name.split())
    return name

class ParseWarning(Warning):
    def __init__(self, parsed, value, **kwargs):
        self.value = value
        self.parsed = parsed
        self.kwargs = kwargs

    def __unicode__(self):
        return self.value

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __repr__(self):
        return str('ParseWarning({}, **{})').format(self, repr(self.kwargs))


def old_assume_quality(guessed_quality, assumed_quality):
    if assumed_quality:
        if not guessed_quality:
            return assumed_quality
        if assumed_quality.resolution:
            guessed_quality.resolution = assumed_quality.resolution
        if assumed_quality.source:
            guessed_quality.source = assumed_quality.source
        if assumed_quality.codec:
            guessed_quality.codec = assumed_quality.codec
        if assumed_quality.audio:
            guessed_quality.audio = assumed_quality.audio
    return guessed_quality


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

default_ignore_prefixes = [
    '(?:\[[^\[\]]*\])',  # ignores group names before the name, eg [foobar] name
    '(?:HD.720p?:)',
    '(?:HD.1080p?:)']


def name_to_re(name, ignore_prefixes=None, parser=None):
    if not ignore_prefixes:
        ignore_prefixes = default_ignore_prefixes
    """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
    parenthetical = None
    if name.endswith(')'):
        p_start = name.rfind('(')
        if p_start != -1:
            parenthetical = re.escape(name[p_start + 1:-1])
            name = name[:p_start - 1]
    # Blanks are any non word characters except & and _
    blank = r'(?:[^\w&]|_)'
    ignore = '(?:' + '|'.join(ignore_prefixes) + ')?'
    res = re.sub(re.compile(blank + '+', re.UNICODE), ' ', name)
    res = res.strip()
    # accept either '&' or 'and'
    res = re.sub(' (&|and) ', ' (?:and|&) ', res, re.UNICODE)
    res = re.sub(' +', blank + '*', res, re.UNICODE)
    if parenthetical:
        res += '(?:' + blank + '+' + parenthetical + ')?'
        # Turn on exact mode for series ending with a parenthetical,
        # so that 'Show (US)' is not accepted as 'Show (UK)'
        if parser:
            parser.strict_name = True
    res = '^' + ignore + blank + '*' + '(' + res + ')(?:\\b|_)' + blank + '*'
    return res


def remove_dirt(name):
    if name:
        name = re.sub(r'[_.,\[\]\(\): ]+', ' ', name).strip().lower()
    return name


def normalize_name(name):
    name = capwords(name)
    return name


class ParsedEntry(ABCMeta(str('ParsedEntryABCMeta'), (object,), {})):
    """
    A parsed entry, containing parsed data like name, year, episodeNumber and season.
    """

    def __init__(self, data, name=None, alternate_names=None, name_regexps=None, ignore_prefixes=None, allow_groups=None, **kwargs):
        self._data = data
        self._name = name
        self._valid = None
        self.name_regexps = name_regexps if name_regexps else []
        self.alternate_names = alternate_names if alternate_names else []
        self.ignore_prefixes = ignore_prefixes if ignore_prefixes else default_ignore_prefixes
        self.allow_groups = allow_groups

    def _validate(self):
        return self._validate_name() and self._validate_groups()

    def _validate_name(self):
        # name end position
        name_start = 0
        name_end = 0

        # regexp name matching
        re_from_name = False
        if not self.name_regexps:
            # if we don't have name_regexps, generate one from the name
            self.name_regexps = ReList(name_to_re(name, self.ignore_prefixes, self) for name in [self.name] + self.alternate_names)
            # With auto regex generation, the first regex group captures the name
            re_from_name = True
        # try all specified regexps on this data
        for name_re in self.name_regexps:
            match = re.search(name_re, self.data)
            if match:
                match_start, match_end = match.span(1 if re_from_name else 0)
                # Always pick the longest matching regex
                if match_end > name_end:
                    name_start, name_end = match_start, match_end
                log.debug('NAME SUCCESS: %s matched to %s', name_re.pattern, self.data)
        if not name_end:
            # leave this invalid
            log.debug('FAIL: name regexps %s do not match %s',
                      [regexp.pattern for regexp in self.name_regexps], self.data)
            return False
        return True

    def _validate_groups(self):
        if not self.allow_groups:
            return True
        return self.release_group in self.allow_groups

    @property
    def name(self):
        return self._name if self._name else self.parsed_name

    @name.setter
    def name(self, name):
        self._valid = None
        self._name = name

    @abstractproperty
    def parsed_name(self):
        raise NotImplementedError

    @property
    def data(self):
        return self._data

    @property
    def valid(self):
        if not self._name:
            return True
        if self._valid is None:
            self._valid = self._validate()
        return self._valid

    @property
    def proper(self):
        return self.proper_count > 0

    @abstractproperty
    def proper_count(self):
        raise NotImplementedError

    @property
    def is_series(self):
        return False

    @property
    def is_movie(self):
        return False

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
    _assumed_quality = None

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
            self._old_quality = self.quality2.to_old_quality(self._assumed_quality)
        return self._old_quality

    def assume_quality(self, quality):
        self._assumed_quality = quality
        self._old_quality = None

    def assume_quality2(self, quality2):
        self._assumed_quality = quality2.to_old_quality()

    def __str__(self):
        return "<%s(name=%s,year=%s)>" % (self.__class__.__name__, self.name, self.year)

    def __cmp__(self, other):
        """Compares quality of parsed, if quality is equal, compares proper_count."""
        return cmp((self.quality), (other.quality))

    def __eq__(self, other):
        return self is other


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

    def to_old_quality(self, assumed_quality=None):
        resolution = self.screen_size
        source = self.format.replace('-', '') if self.format else None
        codec = self.video_codec
        audio = (self.audio_codec + (self.audio_channels if self.audio_channels else '')) if self.audio_codec else None

        old_quality = qualities.Quality(' '.join(filter(None, [resolution, source, codec, audio])))
        old_quality = old_assume_quality(old_quality, assumed_quality)

        return old_quality


    def __str__(self):
        return "<%s(screen_size=%s,source=%s,video_codec=%s,audio_channels=%s)>" % (
        self.__class__.__name__, self.screen_size, self.source, self.video_codec, self.audio_channels)


class ParsedMovie(ABCMeta(str('ParsedMovieABCMeta'), (ParsedVideo,), {})):
    @property
    def parsed_name(self):
        return self.title

    @property
    def title(self):
        raise NotImplementedError

    @property
    def is_movie(self):
        return True


class ParsedSerie(ABCMeta(str('ParsedSerieABCMeta'), (ParsedVideo,), {})):
    @property
    def parsed_name(self):
        return self.series

    @abstractproperty
    def series(self):
        raise NotImplementedError

    @abstractproperty
    def title(self):
        raise NotImplementedError

    @property
    def is_series(self):
        return True

    @abstractproperty
    def season(self):
        raise NotImplementedError

    @abstractproperty
    def episode(self):
        raise NotImplementedError

    @abstractproperty
    def episodes(self):
        raise NotImplementedError

    @abstractproperty
    def episode_details(self):
        raise NotImplementedError

    @abstractproperty
    def is_special(self):
        raise NotImplementedError

    @abstractproperty
    def regexp_id(self):
        raise NotImplementedError

    @property
    def valid(self):
        ret = super(ParsedVideo, self).valid
        if ret:
            if self.regexp_id:
                return True
            if self.is_special:
                return True
            if self.episode and self.season:
                return True
            if self.date:
                return True
            if self.episode and not self.season:
                return True
        return False

    @property
    def id_type(self):
        if self.regexp_id:
            return 'id'
        if self.is_special:
            return 'special'
        if self.episode and self.season:
            return 'ep'
        if self.date:
            return 'date'
        if self.episode and not self.season:
            return 'sequence'
        raise NotImplementedError

    @property
    def id(self):
        if self.regexp_id:
            return self.regexp_id
        if self.is_special:
            return self.title
        if self.date is not None:
            return self.date
        if self.episode is not None:
            return self.episode
        raise NotImplementedError

    @property
    def identifiers(self):
        """Return all identifiers this parser represents. (for packs)"""
        # Currently 'ep' is the only id type that supports packs
        if not self.valid:
            raise Exception('Series flagged invalid')
        if self.id_type == 'ep':
            return ['S%02dE%02d' % (self.season, self.episode + x) for x in xrange(self.episodes)]
        elif self.id_type == 'date':
            return [self.id.strftime('%Y-%m-%d')]
        if self.id is None:
            raise Exception('Series is missing identifier')
        else:
            return [self.id]

    @property
    def identifier(self):
        """Return String identifier for parsed episode, eg. S01E02
        (will be the first identifier if this is a pack)
        """
        return self.identifiers[0]

    @property
    def pack_identifier(self):
        """Return a combined identifier for the whole pack if this has more than one episode."""
        # Currently only supports ep mode
        if self.id_type == 'ep' and self.episodes > 1:
            return 'S%02dE%02d-E%02d' % (self.season, self.episode, self.episode + self.episodes - 1)
        else:
            return self.identifier

    def __str__(self):
        return "<%s(name=%s,season=%s,episode=%s)>" % (self.__class__.__name__, self.name, self.season,
                                                       self.episodes if self.episodes and len(
                                                           self.episodes) > 1 else self.episode)

    def __cmp__(self, other):
        """Compares quality of parsers, if quality is equal, compares proper_count."""
        return cmp((self.quality, self.episodes, self.proper_count),
                   (other.quality, other.episodes, other.proper_count))

    def __eq__(self, other):
        return self is other


class Parser(ABCMeta(str('ParserABCMeta'), (object,), {})):
    @abstractmethod
    def parse(self, input_, type_=None, name=None, **kwargs):
        """
        :param input_: string to parse
        :param type_: a PARSER_* type
        :param attended_name: an attended name, or None is unknown
        :raises ParseWarning

        :return: an instance of :class:`ParsedEntry`
        """
        raise NotImplementedError

