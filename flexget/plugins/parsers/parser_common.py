from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
from string import capwords

from flexget.utils.qualities import Quality

log = logging.getLogger('parser')

SERIES_ID_TYPES = ['ep', 'date', 'sequence', 'id']


def clean_value(name):
    for char in '[]()_,.':
        name = name.replace(char, ' ')

    # if there are no spaces
    if name.find(' ') == -1:
        name = name.replace('-', ' ')

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
    '(?:HD.1080p?:)',
    '(?:HD.2160p?:)'
]


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


class MovieParseResult(object):
    def __init__(self, data=None, name=None, year=None, quality=None, proper_count=0, release_group=None, valid=True):
        self.name = name
        self.data = data
        self.year = year
        self.quality = quality if quality is not None else Quality()
        self.proper_count = proper_count
        self.release_group = release_group
        self.valid = valid

    @property
    def identifier(self):
        if self.name and self.year:
            return ('%s %s' % (self.name, self.year)).strip().lower()
        elif self.name:
            return self.name.lower()

    @property
    def proper(self):
        return self.proper_count > 0

    @property
    def fields(self):
        """
        Return a dict of all parser fields
        """
        return {
            'id': self.identifier,
            'movie_parser': self,
            'movie_name': self.name,
            'movie_year': self.year,
            'proper': self.proper,
            'proper_count': self.proper_count,
            'release_group': self.release_group
        }

    def __str__(self):
        valid = 'OK' if self.valid else 'INVALID'
        return '<MovieParseResult(data=%s,name=%s,year=%s,id=%s,quality=%s,proper=%s,release_group=%s,status=%s)>' % \
               (self.data, self.name, self.year, self.identifier, self.quality, self.proper_count, self.release_group,
                valid)


class SeriesParseResult(object):
    def __init__(self,
                 data=None,
                 name=None,
                 identified_by=None,
                 id_type=None,
                 id=None,
                 episodes=1,
                 season_pack=False,
                 strict_name=False,
                 quality=None,
                 proper_count=0,
                 special=False,
                 group=None,
                 valid=True
                 ):
        self.name = name
        self.data = data
        self.episodes = episodes
        self.season_pack = season_pack
        self.identified_by = identified_by
        self.id = id
        self.id_type = id_type
        self.quality = quality if quality is not None else Quality()
        self.proper_count = proper_count
        self.special = special
        self.group = group
        self.valid = valid
        self.strict_name = strict_name

    @property
    def proper(self):
        return self.proper_count > 0

    @property
    def season(self):
        if self.id_type == 'ep':
            return self.id[0]
        if self.id_type == 'date':
            return self.id.year
        if self.id_type == 'sequence':
            return 0
        return None

    @property
    def episode(self):
        if self.id_type == 'ep':
            return self.id[1]
        if self.id_type == 'sequence':
            return self.id
        return None

    @property
    def identifiers(self):
        """Return all identifiers this parser represents. (for packs)"""
        # Currently 'ep' is the only id type that supports packs
        if not self.valid:
            raise Exception('Series flagged invalid')
        if self.id_type == 'ep':
            if self.season_pack:
                return ['S%02d' % self.season]
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
        if self.id_type == 'ep':
            if self.episodes > 1:
                return 'S%02dE%02d-E%02d' % (self.season, self.episode, self.episode + self.episodes - 1)
            else:
                return self.identifier
        else:
            return self.identifier

    def __str__(self):
        valid = 'OK' if self.valid else 'INVALID'
        return '<SeriesParseResult(data=%s,name=%s,id=%s,season=%s,season_pack=%s,episode=%s,quality=%s,proper=%s,' \
               'special=%s,status=%s)>' % \
               (self.data, self.name, str(self.id), self.season, self.season_pack, self.episode, self.quality,
                self.proper_count, self.special, valid)
