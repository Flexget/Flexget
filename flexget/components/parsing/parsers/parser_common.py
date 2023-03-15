import datetime
import re
from string import capwords
from typing import List, Optional, Tuple, Union

from loguru import logger

from flexget.utils.qualities import Quality

logger = logger.bind(name='parser')

SERIES_ID_TYPES = ['ep', 'date', 'sequence', 'id']


def clean_value(name: str) -> str:
    for char in '[]()_,.':
        name = name.replace(char, ' ')

    # if there are no spaces
    if name.find(' ') == -1:
        name = name.replace('-', ' ')

    # MovieParser.strip_spaces
    name = ' '.join(name.split())
    return name


def old_assume_quality(guessed_quality: Quality, assumed_quality: Quality) -> Quality:
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


def remove_dirt(name: str) -> str:
    if name:
        name = re.sub(r'[_.,\[\]\(\): ]+', ' ', name).strip().lower()
    return name


def normalize_name(name: str) -> str:
    name = capwords(name)
    return name


class MovieParseResult:
    def __init__(
        self,
        data: str = None,
        name: str = None,
        year: Optional[int] = None,
        quality: Quality = None,
        proper_count: int = 0,
        release_group: Optional[str] = None,
        valid: bool = True,
    ) -> None:
        self.name: str = name
        self.data: str = data
        self.year: Optional[int] = year
        self.quality: Quality = quality if quality is not None else Quality()
        self.proper_count: int = proper_count
        self.release_group: Optional[str] = release_group
        self.valid: bool = valid

    @property
    def identifier(self) -> str:
        if self.name and self.year:
            return ('%s %s' % (self.name, self.year)).strip().lower()
        elif self.name:
            return self.name.lower()

    @property
    def proper(self) -> bool:
        return self.proper_count > 0

    @property
    def fields(self) -> dict:
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
            'release_group': self.release_group,
        }

    def __str__(self) -> str:
        valid = 'OK' if self.valid else 'INVALID'
        return (
            '<MovieParseResult(data=%s,name=%s,year=%s,id=%s,quality=%s,proper=%s,release_group=%s,status=%s)>'
            % (
                self.data,
                self.name,
                self.year,
                self.identifier,
                self.quality,
                self.proper_count,
                self.release_group,
                valid,
            )
        )


class SeriesParseResult:
    def __init__(
        self,
        data: str = None,
        name: str = None,
        identified_by: str = None,
        id_type: str = None,
        id: Union[Tuple[int, int], str, int, datetime.date] = None,
        episodes: int = 1,
        season_pack: bool = False,
        strict_name: bool = False,
        quality: Quality = None,
        proper_count: int = 0,
        special: bool = False,
        group: Optional[str] = None,
        valid: bool = True,
    ) -> None:
        self.name: str = name
        self.data: str = data
        self.episodes: int = episodes
        self.season_pack: bool = season_pack
        self.identified_by: str = identified_by
        self.id: Union[Tuple[int, int], str, int, datetime.date] = id
        self.id_type: str = id_type
        self.quality: Quality = quality if quality is not None else Quality()
        self.proper_count: int = proper_count
        self.special: bool = special
        self.group: Optional[str] = group
        self.valid: bool = valid
        self.strict_name: bool = strict_name

    @property
    def proper(self) -> bool:
        return self.proper_count > 0

    @property
    def season(self) -> Optional[int]:
        if self.id_type == 'ep':
            return self.id[0]
        if self.id_type == 'date':
            return self.id.year
        if self.id_type == 'sequence':
            return 0
        return None

    @property
    def episode(self) -> Optional[int]:
        if self.id_type == 'ep':
            return self.id[1]
        if self.id_type == 'sequence':
            return self.id
        return None

    @property
    def identifiers(self) -> List[str]:
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
    def identifier(self) -> str:
        """Return String identifier for parsed episode, eg. S01E02
        (will be the first identifier if this is a pack)
        """
        return self.identifiers[0]

    @property
    def pack_identifier(self) -> str:
        """Return a combined identifier for the whole pack if this has more than one episode."""
        # Currently only supports ep mode
        if self.id_type == 'ep':
            if self.episodes > 1:
                return 'S%02dE%02d-E%02d' % (
                    self.season,
                    self.episode,
                    self.episode + self.episodes - 1,
                )
            else:
                return self.identifier
        else:
            return self.identifier

    def __str__(self) -> str:
        valid = 'OK' if self.valid else 'INVALID'
        return (
            '<SeriesParseResult(data=%s,name=%s,id=%s,season=%s,season_pack=%s,episode=%s,quality=%s,proper=%s,'
            'special=%s,status=%s)>'
            % (
                self.data,
                self.name,
                str(self.id),
                self.season,
                self.season_pack,
                self.episode,
                self.quality,
                self.proper_count,
                self.special,
                valid,
            )
        )
