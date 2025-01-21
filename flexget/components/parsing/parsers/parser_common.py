import datetime
import re
from string import capwords
from typing import Optional, Union

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
    return ' '.join(name.split())


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
    return re.sub(r'[_.,\[\]\(\): ]+', ' ', name).strip().lower() if name else name


def normalize_name(name: str) -> str:
    return capwords(name)


class MovieParseResult:
    def __init__(
        self,
        data: Optional[str] = None,
        name: Optional[str] = None,
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
        if self.name:
            return (f'{self.name} {self.year}').strip().lower() if self.year else self.name.lower()
        return None

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
            f'<MovieParseResult(data={self.data},name={self.name},year={self.year},'
            f'id={self.identifier},quality={self.quality},proper={self.proper_count},'
            f'release_group={self.release_group},status={valid})>'
        )


class SeriesParseResult:
    def __init__(
        self,
        data: Optional[str] = None,
        name: Optional[str] = None,
        identified_by: Optional[str] = None,
        id_type: Optional[str] = None,
        id: Optional[Union[tuple[int, int], str, int, datetime.date]] = None,
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
        self.id: Union[tuple[int, int], str, int, datetime.date] = id
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
        # TODO Use match-case statement after Python 3.9 is dropped
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
    def identifiers(self) -> list[str]:
        """Return all identifiers this parser represents. (for packs)"""
        # Currently 'ep' is the only id type that supports packs
        if not self.valid:
            raise Exception('Series flagged invalid')
        if self.id_type == 'ep':
            return (
                [f'S{self.season:02d}']
                if self.season_pack
                else [f'S{self.season:02d}E{self.episode + x:02d}' for x in range(self.episodes)]
            )
        if self.id_type == 'date':
            return [self.id.strftime('%Y-%m-%d')]
        if self.id is None:
            raise Exception('Series is missing identifier')
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
        return (
            f'S{self.season:02d}E{self.episode:02d}-E{self.episode + self.episodes - 1:02d}'
            if self.id_type == 'ep' and self.episodes > 1
            else self.identifier
        )

    def __str__(self) -> str:
        valid = 'OK' if self.valid else 'INVALID'
        return (
            f'<SeriesParseResult(data={self.data},name={self.name},id={self.id!s},season={self.season},'
            f'season_pack={self.season_pack},episode={self.episode},quality={self.quality},'
            f'proper={self.proper_count},special={self.special},status={valid})>'
        )
