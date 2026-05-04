from __future__ import annotations

import functools
import logging
import lzma
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from requests_cache import CachedSession, SerializerPipeline, Stage, pickle_serializer
from sqlalchemy import Column, Integer, Unicode, delete

from flexget import db_schema, plugin
from flexget.event import event
from flexget.log import logger
from flexget.manager import Session as DBSession
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TokenBucketLimiter

if TYPE_CHECKING:
    from requests import Response
    from typing_extensions import NotRequired, TypedDict

    from flexget.entry import Entry
    from flexget.manager import Task
    from flexget.utils.sqlalchemy_utils import ContextSession

    class EntryType(TypedDict):
        anidb_id: int
        anilist_id: NotRequired[int]
        mal_id: NotRequired[int]
        animecountdown_id: NotRequired[int]
        ann_id: NotRequired[int]
        animeplanet_id: NotRequired[str]
        anisearch_id: NotRequired[int]
        imdb_id: NotRequired[str]
        kitsu_id: NotRequired[int]
        livechart_id: NotRequired[int]
        simkl_id: NotRequired[int]
        tmdb_id: NotRequired[int]
        tmdb_offset: NotRequired[int]
        tmdb_season: NotRequired[int]
        tvdb_id: NotRequired[int]
        tvdb_offset: NotRequired[int]
        tvdb_season: NotRequired[int]

    class DBType(TypedDict):
        anidb: int
        anilist: NotRequired[int]
        myanimelist: NotRequired[int]
        animecountdown: NotRequired[int]
        animenewsnetwork: NotRequired[int]
        animeplanet: NotRequired[str]
        anisearch: NotRequired[int]
        imdb: NotRequired[str]
        kitsu: NotRequired[int]
        livechart: NotRequired[int]
        simkl: NotRequired[int]
        tmdb: NotRequired[int]
        tmdb_offset: NotRequired[int]
        tmdb_season: NotRequired[int]
        tvdb: NotRequired[int]
        tvdb_offset: NotRequired[int]
        tvdb_season: NotRequired[int]


logger = logger.bind(name='anime_relations')
logging.getLogger('requests_cache').setLevel(logging.WARNING)  # Suppress Requests-Cache logs

CACHE_DURATION = timedelta(days=7)
GH_RAW_FILE = 'https://raw.githubusercontent.com/{repo}/master/{file}'
###  FIELD MAPS  ###
XML_TO_DB = {
    'anidbid': 'anidb',
    'tvdbid': 'tvdb',
    'defaulttvdbseason': 'tvdb_season',
    'episodeoffset': 'tvdb_offset',
    'tmdbtv': 'tmdb',
    'tmdbseason': 'tmdb_season',
    'tmdboffset': 'tmdb_offset',
    'tmdbid': 'tmdb',
    'imdbid': 'imdb',
}
JSON_TO_DB = {
    'anidb_id': 'anidb',
    'anilist_id': 'anilist',
    'mal_id': 'myanimelist',
    'animecountdown_id': 'animecountdown',
    'animenewsnetwork_id': 'animenewsnetwork',
    'anime-planet_id': 'animeplanet',
    'anisearch_id': 'anisearch',
    'imdb_id': 'imdb',
    'kitsu_id': 'kitsu',
    'livechart_id': 'livechart',
    'simkl_id': 'simkl',
    'themoviedb_id': 'tmdb',
    'season.tmdb': 'tmdb_season',
    'episodes_offset.tmdb': 'tmdb_offset',
    'tvdb_id': 'tvdb',
    'season.tvdb': 'tvdb_season',
    'episodes_offset.tvdb': 'tvdb_offset',
}
DB_TO_ENTRY = {
    'anidb': 'anidb_id',
    'anilist': 'al_id',
    'myanimelist': 'mal_id',
    'animecountdown': 'animecountdown_id',
    'animenewsnetwork': 'ann_id',
    'animeplanet': 'animeplanet_id',
    'anisearch': 'anisearch_id',
    'imdb': 'imdb_id',
    'kitsu': 'kitsu_id',
    'livechart': 'livechart_id',
    'simkl': 'simkl_id',
    'tmdb': 'tmdb_id',
    'tmdb_offset': 'tmdb_offset',
    'tmdb_season': 'tmdb_season',
    'tvdb': 'tvdb_id',
    'tvdb_offset': 'tvdb_offset',
    'tvdb_season': 'tvdb_season',
}
ENTRY_TO_DB = {v: k for k, v in DB_TO_ENTRY.items()}

Base = db_schema.versioned_base('anime_relations', 0)


class AnimeRelationsDB(Base):
    __tablename__ = 'anime_relations'

    anidb = Column(
        Integer, primary_key=True, autoincrement='ignore_fk', nullable=False, unique=True
    )
    anilist = Column(Integer)
    myanimelist = Column(Integer)
    animecountdown = Column(Integer)
    animenewsnetwork = Column(Integer)
    animeplanet = Column(Unicode)
    anisearch = Column(Integer)
    imdb = Column(Unicode)
    kitsu = Column(Integer)
    livechart = Column(Integer)
    simkl = Column(Integer)
    tmdb = Column(Integer)
    tmdb_offset = Column(Integer)
    tmdb_season = Column(Integer)
    tvdb = Column(Integer)
    tvdb_offset = Column(Integer)
    tvdb_season = Column(Integer)

    def as_dict(self) -> DBType:
        dbr: DBType = {'anidb': 0}
        for k, v in self.__dict__.items():
            if k in DB_TO_ENTRY:
                dbr[k] = v
        return dbr

    def __repr__(self):
        return '<RelationsDB({})>'.format(
            ', '.join([f'{k}={v}' for k, v in self.as_dict().items()])
        )


class AnimeRelations:
    """Anime Relations plugin."""

    schema = {
        'type': 'boolean',
        'additionalProperties': False,
    }

    cached = True

    def on_task_metainfo(self, task: Task, config: bool):
        if not config:
            return
        self.cached = not task.options.nocache

        self.uncached_session = RequestSession()
        self.uncached_session.add_domain_limiter(
            TokenBucketLimiter('githubusercontent.com', 60, '1 hour')
        )

        if self.cached:
            self.cached_session = CachedSession(
                Path(task.manager.config_base, 'cached_requests'),
                cache_control=False,
                ignored_parameters=['expires', 'max-age'],
                expire_after=CACHE_DURATION,
                stale_if_error=True,
                backend='filesystem',
                serializer=SerializerPipeline(
                    [pickle_serializer, Stage(dumps=lzma.compress, loads=lzma.decompress)],
                    is_binary=True,
                ),
            )
            self.cached_session.headers.update(self.uncached_session.headers)
            self.cached_session.cache.delete(older_than=CACHE_DURATION)
            self.cached_session.cache.delete(invalid=True)

        with DBSession() as session:
            history = session.query(AnimeRelationsDB).filter_by(anidb=0).first()
            self.history = None if history is None else history.as_dict()
        logger.debug('History: {}', self.history)

        relations = self.populate_relations()

        if (
            self.history is None
            # Exploiting Unicode fields to avoid creating another table for ETags
            or relations[0].get('imdb') != self.history.get('imdb')
            or relations[0].get('animeplanet') != self.history.get('animeplanet')
        ):
            with DBSession() as session:
                session.execute(delete(AnimeRelationsDB))
                session.add_all([self.compile_db_entry(rel) for rel in relations])
                history = session.query(AnimeRelationsDB).filter_by(anidb=0).first()
                self.history = None if history is None else history.as_dict()

        for entry in task.entries:
            for field in ENTRY_TO_DB:
                if entry.get(field, eval_lazy=False) is None:
                    continue
                with DBSession() as session:
                    db_entry = self.db_query(session, field, entry)
                    if not db_entry:
                        logger.debug(
                            'No matches for {}={}: `{}`', field, entry[field], entry['title']
                        )

                if not db_entry:
                    logger.verbose(  # pyright: ignore[reportAttributeAccessIssue]  Verbose logging isn't typed
                        'No Relations for `{}`', entry['title']
                    )
                    break
                logger.verbose(  # pyright: ignore[reportAttributeAccessIssue]  Verbose logging isn't typed
                    'Relations for {}={} `{}`: {}',
                    field,
                    entry[field],
                    entry['title'],
                    db_entry,
                )
                entry.update_using_map(ENTRY_TO_DB, db_entry, ignore_none=True)
                entry['relations'] = db_entry
                break

    def compile_db_entry(self, entry: DBType) -> AnimeRelationsDB:
        relation = AnimeRelationsDB()
        for k, v in entry.items():
            setattr(relation, k, v)
        return relation

    def db_query(self, session: ContextSession, field: str, entry: Entry) -> DBType | None:
        result = session.query(AnimeRelationsDB)
        column: Column[int] | Column[str] = getattr(AnimeRelationsDB, ENTRY_TO_DB[field])
        if not field.endswith('_id'):
            return None
        if field == 'imdb_id':
            result = (
                result.filter(
                    column.like(f'%{entry[field]}%')
                )  # Movie fields can have multiple IDs split by commas
                # but can't wildcard TMDB because they can have as few a 2 digits
            )
        else:
            result = result.filter(column == entry[field])
        if field in ('tvdb_id', 'tmdb_id'):
            # Try to search for season to narrow it further
            season = entry.get(field.replace('id', 'season'), entry.get('series_season'))
            if season is not None:
                result = (
                    result.filter(
                        getattr(AnimeRelationsDB, ENTRY_TO_DB[field.replace('id', 'season')])
                        == season
                    )
                    if season is not None
                    else result
                )
        result = result.order_by(AnimeRelationsDB.anidb.desc()).first()  # Return the newest entry
        return result.as_dict() if result is not None else None

    def populate_relations(self) -> list[DBType]:
        entries: list[DBType] = [
            *self.parse_json(),
            *self.parse_xml(),
        ]

        # Merge fields together based on AniDB
        filter: dict[str, DBType] = {
            str(entry['anidb']): {'anidb': entry['anidb']} for entry in entries
        }
        for entry in entries:
            idx = str(entry['anidb'])
            for k, v in entry.items():
                # Ignore TVDB IDs like 'movie', 'ova', 'tv special', etc...
                if k == 'tvdb' and not str(v).isdigit():
                    continue
                # Absolute season becomes 1
                if v == 'a' and k in ('tmdb_season', 'tvdb_season'):
                    v = 1
                filter[idx][k] = v
        unique: list[DBType] = list(filter.values())
        logger.debug('{} Unique entries', len(filter))
        return unique

    def parse_json(self) -> list[DBType]:
        request: Response = self.get(
            GH_RAW_FILE.format(repo='fribb/anime-lists', file='anime-list-mini.json'),
            etag=self.history.get('imdb', '') if self.history else '',
        )
        entries: list[DBType] = [{'anidb': 0, 'imdb': request.headers.get('ETag', '')}]
        for anime in request.json():
            if not anime.get('anidb_id'):
                continue
            new_entry: DBType = {'anidb': 99999999}
            for json_key, db_key in JSON_TO_DB.items():
                val = functools.reduce(lambda x, y: dict.get(x, y, {}), json_key.split('.'), anime)
                if val is None or all((repr(val) == r'{}', isinstance(val, dict))):
                    continue
                new_entry[db_key] = val
            entries.append(new_entry)
        logger.debug('{} JSON anime', len(entries))
        return entries

    def parse_xml(self) -> list[DBType]:
        response: Response = self.get(
            GH_RAW_FILE.format(repo='Anime-Lists/anime-lists', file='anime-list.xml'),
            etag=self.history.get('animeplanet', '') if self.history else '',
        )
        root = ET.fromstring(response.content.decode(encoding='utf-8'))
        items: list[DBType] = [
            {'anidb': 0, 'animeplanet': response.headers.get('ETag', '')},
            *[
                {
                    XML_TO_DB[key]: int(val) if val.isdigit() else val
                    for key, val in anime.attrib.items()
                    if key in XML_TO_DB
                }
                for anime in root.findall('anime')
            ],  # pyright: ignore[reportAssignmentType]
        ]
        # Type check fails because list comprehension can't verify AniDB field but it is always present on the XML
        logger.debug('{} XML anime', len(items))
        return items

    def get(self, url: str, *, etag: str) -> Response:
        headers = {'Cache-Control': f'max-age={CACHE_DURATION.seconds}'}
        if self.cached:
            session = self.cached_session
            if etag:
                headers['If-None-Match'] = etag
            logger.debug('GETing {}', url)
        else:
            session = self.uncached_session

        resp = session.get(url, headers=headers)
        if getattr(resp, 'from_cache', None):
            logger.debug('Request was cached!')
        return resp


@event('plugin.register')
def register_plugin():
    plugin.register(AnimeRelations, 'anime_relations', api_ver=2)
