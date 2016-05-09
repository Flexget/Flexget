from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import native_str
from past.builtins import cmp

import logging
import re
from abc import abstractproperty, abstractmethod, ABCMeta
from string import capwords

from flexget.utils.tools import ReList


log = logging.getLogger('parser')

SERIES_ID_TYPES = ['ep', 'date', 'sequence', 'id']


def clean_value(name):
    # Move anything in leading brackets to the end
    # name = re.sub(r'^\[(.*?)\](.*)', r'\2 \1', name)

    for char in '[]()_,.':
        name = name.replace(char, ' ')

    # if there are no spaces
    if name.find(' ') == -1:
        name = name.replace('-', ' ')

    # remove unwanted words (imax, ..)
    # self.remove_words(data, self.remove)

    # MovieParser.strip_spaces
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


default_ignore_prefixes = [
    '(?:\[[^\[\]]*\])',  # ignores group names before the name, eg [foobar] name
    '(?:HD.720p?:)',
    '(?:HD.1080p?:)']


def name_to_re(name, ignore_prefixes=None, parser=None):
    """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
    if not ignore_prefixes:
        ignore_prefixes = default_ignore_prefixes
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


class ParsedEntry(ABCMeta(native_str('ParsedEntryABCMeta'), (object,), {})):
    """
    A parsed entry, containing parsed data like name, year, episodeNumber and season.
    """

    def __init__(self, data, name, **kwargs):
        self._data = data
        self._name = name
        self._validated_name = None
        self._kwargs = kwargs

    @property
    def name_regexps(self):
        return self._kwargs['name_regexps'] if 'name_regexps' in self._kwargs else []

    @property
    def alternate_names(self):
        return self._kwargs['alternate_names'] if 'alternate_names' in self._kwargs else []

    @property
    def ignore_prefixes(self):
        return self._kwargs['ignore_prefixes'] if 'ignore_prefixes' in self._kwargs else default_ignore_prefixes

    @property
    def allow_groups(self):
        return self._kwargs['allow_groups'] if 'allow_groups' in self._kwargs else []

    @property
    def strict_name(self):
        return self._kwargs['strict_name'] if 'strict_name' in self._kwargs else False

    @abstractproperty
    def parsed_type(self):
        raise NotImplementedError

    @abstractproperty
    def type(self):
        raise NotImplementedError

    def _validate(self):
        validate_name = self._validate_name()
        if validate_name and self._validate_groups():
            return validate_name
        return None

    def _validate_name(self):
        # name end position
        name_start = 0
        name_end = 0

        # regexp name matching
        re_from_name = False
        name_regexps = ReList(self.name_regexps)
        if not name_regexps:
            # if we don't have name_regexps, generate one from the name
            name_regexps = ReList(name_to_re(name,
                                             self.ignore_prefixes,
                                             None) for name in [self.name] + self.alternate_names)
            # With auto regex generation, the first regex group captures the name
            re_from_name = True
        # try all specified regexps on this data
        for name_re in name_regexps:
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
                      [regexp.pattern for regexp in name_regexps], self.data)
            return ''
        return clean_value(self.data[name_start:name_end])

    def _validate_groups(self):
        if not self.allow_groups:
            return True
        if not self.group:
            return False
        return self.group.lower() in [x.lower() for x in self.allow_groups]

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
        if not self.parsed_name:
            return False
        if self.type != self.parsed_type:
            return False
        if not self._name:
            return True  # Not False ???!
        if self._validated_name is None:
            self._validated_name = self._validate()
        if self.strict_name and self._validated_name != clean_value(self.parsed_name):
            return False
        return len(self._validated_name) > 0 if self._validated_name else False

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

    @property
    def group(self):
        return self.parsed_group.lower() if self.parsed_group else None

    @abstractproperty
    def parsed_group(self):
        raise NotImplementedError

    @abstractproperty
    def properties(self):
        raise NotImplementedError

    def __str__(self):
        return "<%s(name=%s)>" % (self.__class__.__name__, self.name)


class ParsedVideo(ABCMeta(native_str('ParsedVideoABCMeta'), (ParsedEntry,), {})):
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
    def type(self):
        return 'video'

    @property
    def quality(self):
        if not self._old_quality:
            self._old_quality = self.quality2.to_old_quality(self._assumed_quality)
        return self._old_quality

    def assume_quality(self, quality):
        self._assumed_quality = quality
        self._old_quality = None

    def assume_quality2(self, quality2):
        self._assumed_quality = quality2.to_old_quality()

    def __str__(self):
        return "<%s(name=%s,year=%s,quality=%s)>" % (self.__class__.__name__, self.name, self.year, self.quality)

    def __cmp__(self, other):
        """Compares quality of parsed, if quality is equal, compares proper_count."""
        return cmp((self.quality), (other.quality))

    def __eq__(self, other):
        return self is other


class ParsedVideoQuality(ABCMeta(native_str('ParsedVideoQualityABCMeta'), (object,), {})):
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

    @abstractmethod
    def to_old_quality(self, assumed_quality=None):
        raise NotImplementedError

    def __str__(self):
        return "<%s(screen_size=%s,source=%s,video_codec=%s,audio_channels=%s)>" % (
            self.__class__.__name__, self.screen_size, self.source, self.video_codec, self.audio_channels)


class ParsedMovie(ABCMeta(native_str('ParsedMovieABCMeta'), (ParsedVideo,), {})):
    @property
    def parsed_name(self):
        return self.title

    @property
    def type(self):
        return 'movie'

    @property
    def title(self):
        raise NotImplementedError

    @property
    def is_movie(self):
        return True


class ParsedSerie(ABCMeta(native_str('ParsedSerieABCMeta'), (ParsedVideo,), {})):
    _valid_strict = None

    @property
    def allow_seasonless(self):
        return self._kwargs['allow_seasonless'] if 'allow_seasonless' in self._kwargs else False

    @property
    def identified_by(self):
        return self._kwargs['identified_by'] if 'identified_by' in self._kwargs else 'auto'

    @property
    def assume_special(self):
        return self._kwargs['assume_special'] if 'assume_special' in self._kwargs else False

    @property
    def prefer_specials(self):
        return self._kwargs['prefer_specials'] if 'prefer_specials' in self._kwargs else False

    @property
    def parsed_name(self):
        return self.series

    @property
    def type(self):
        return 'series'

    @abstractproperty
    def parsed_season(self):
        raise NotImplementedError

    @abstractproperty
    def country(self):
        raise NotImplementedError

    @abstractproperty
    def series(self):
        raise NotImplementedError

    @abstractproperty
    def title(self):
        raise NotImplementedError

    @abstractproperty
    def complete(self):
        raise NotImplementedError

    @property
    def is_series(self):
        return True

    @property
    def season(self):
        return 1 if not self.parsed_season and self.allow_seasonless else self.parsed_season

    @abstractproperty
    def episode(self):
        raise NotImplementedError

    @abstractproperty
    def episodes(self):
        raise NotImplementedError

    @abstractproperty
    def date(self):
        raise NotImplementedError

    @abstractproperty
    def episode_details(self):
        raise NotImplementedError

    @abstractproperty
    def special(self):
        raise NotImplementedError

    @abstractproperty
    def regexp_id(self):
        raise NotImplementedError

    @abstractproperty
    def valid_strict(self):
        raise NotImplementedError

    @property
    def valid(self):
        ret = super(ParsedVideo, self).valid
        if ret:
            if self.country and self.name.endswith(')'):
                p_start = self.name.rfind('(')
                if p_start != -1:
                    parenthetical = re.escape(self.name[p_start + 1:-1])
                    if parenthetical and parenthetical.lower() != self.country.lower():
                        return False
            if self.identified_by != 'auto' and self.identified_by != self.id_type:
                return False
            if self.complete or (self.identified_by in ['auto', 'ep'] and
                                 self.season is not None and self.episode is None):
                return False
            if self.identified_by in ['auto', 'ep'] and self.episodes > 3:
                return False
            if self.identified_by in ['ep', 'sequence'] and self.episode is None:
                return False
            if self.identified_by == 'ep' and (self.episode is None or (self.season is None and
                                                                        not self.allow_seasonless)):
                return False
            if self.identified_by == 'date' and not self.date:
                return False
            if self.special or self.assume_special:
                return True
            if self.regexp_id:
                return True
            if self.episode is not None or self.season is not None:
                return True
            if self.date:
                return True
            if self.episode is not None and not self.season:
                return True
        return False

    @property
    def id_type(self):
        id_type = None
        if self.regexp_id:
            id_type = 'id'
        elif self.episode is not None:
            if self.season is not None:
                id_type = 'ep'
            else:
                id_type = 'sequence'
        elif self.date:
            id_type = 'date'
        if self.special or self.assume_special:
            if not id_type or self.prefer_specials:
                id_type = 'special'
        return id_type

    @property
    def id(self):
        id = None
        if self.regexp_id:
            id = self.regexp_id
        elif self.episode is not None:
            id = self.episode
        elif self.date:
            id = self.date
        if self.special or self.assume_special:
            if not id or self.prefer_specials:
                id = self.title if self.title else 'special'
        return id

    @property
    def identifiers(self):
        """Return all identifiers this parser represents. (for packs)"""
        # Currently 'ep' is the only id type that supports packs
        if not self.valid:
            raise Exception('Series flagged invalid')
        if self.id_type == 'ep':
            return ['S%02dE%02d' % (self.season, self.episode + x) for x in range(self.episodes)]
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
        return "<%s(name=%s,id=%s,season=%s,episode=%s,quality=%s,proper=%s,status=%s)>" % \
               (self.__class__.__name__, self.name, self.id, self.season, self.episode,
                self.quality, self.proper_count, 'OK' if self.valid else 'INVALID')

    def __cmp__(self, other):
        """Compares quality of parsers, if quality is equal, compares proper_count."""
        return cmp((self.quality, self.episodes, self.proper_count),
                   (other.quality, other.episodes, other.proper_count))

    def __eq__(self, other):
        return self is other
