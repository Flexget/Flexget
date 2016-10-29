from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re
from string import capwords

from flexget.utils.qualities import Quality

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


class MovieParseResult(object):
    def __init__(self, data=None, name=None, year=None, quality=None, proper_count=0, valid=True):
        self.name = name
        self.data = data
        self.year = year
        self.quality = quality if quality is not None else Quality()
        self.proper_count = proper_count
        self.valid = valid


class SeriesParseResult(object):
    def __init__(self,
                 data=None,
                 name=None,
                 id_type=None,
                 id=None,
                 episodes=1,
                 quality=None,
                 proper_count=0,
                 special=False,
                 group=None,
                 valid=True
                 ):
        self.data = data
        self.name = name
        self.id_type = id_type
        self.id = id
        self.episodes = episodes
        self.quality = quality if quality is not None else Quality()
        self.proper_count = proper_count
        self.special = special
        self.group = group
        self.valid = valid

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
        if self.id_type == 'ep':
            return ['S%02dE%02d' % (self.season, self.episode + x) for x in range(self.episodes)]
        elif self.id_type == 'date':
            return [self.id.strftime('%Y-%m-%d')]
        elif self.id_type == 'sequence':
            return [self.id + x for x in range(self.episode)]
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
        if self.episodes > 1:
            if self.id_type == 'ep':
                return 'S%02dE%02d-E%02d' % (self.season, self.episode, self.episode + self.episodes - 1)
            if self.id_type == 'sequence':
                return '%d-%d' % (self.id, self.id + self.episodes - 1)
        return self.identifier
