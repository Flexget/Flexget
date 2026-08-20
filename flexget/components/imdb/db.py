from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Column, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey, Index

from flexget import db_schema
from flexget.components.imdb.utils import extract_id
from flexget.db_schema import UpgradeImpossible

logger = logger.bind(name='imdb.db')

SCHEMA_VER = 10

Base = db_schema.versioned_base('imdb_lookup', SCHEMA_VER)

# association tables
genres_table = Table(
    'imdb_movie_genres',
    Base.metadata,
    Column('movie_id', ForeignKey('imdb_movies.id')),
    Column('genre_id', ForeignKey('imdb_genres.id')),
    Index('ix_imdb_movie_genres', 'movie_id', 'genre_id'),
)
Base.register_table(genres_table)

actors_table = Table(
    'imdb_movie_actors',
    Base.metadata,
    Column('movie_id', ForeignKey('imdb_movies.id')),
    Column('actor_id', ForeignKey('imdb_actors.id')),
    Index('ix_imdb_movie_actors', 'movie_id', 'actor_id'),
)
Base.register_table(actors_table)

directors_table = Table(
    'imdb_movie_directors',
    Base.metadata,
    Column('movie_id', ForeignKey('imdb_movies.id')),
    Column('director_id', ForeignKey('imdb_directors.id')),
    Index('ix_imdb_movie_directors', 'movie_id', 'director_id'),
)
Base.register_table(directors_table)

writers_table = Table(
    'imdb_movie_writers',
    Base.metadata,
    Column('movie_id', ForeignKey('imdb_movies.id')),
    Column('writer_id', ForeignKey('imdb_writers.id')),
    Index('ix_imdb_movie_writers', 'movie_id', 'writer_id'),
)
Base.register_table(writers_table)

plot_keywords_table = Table(
    'imdb_movie_plot_keywords',
    Base.metadata,
    Column('movie_id', ForeignKey('imdb_movies.id')),
    Column('keyword_id', ForeignKey('imdb_plot_keywords.id')),
    Index('ix_imdb_movie_plot_keywords', 'movie_id', 'keyword_id'),
)
Base.register_table(plot_keywords_table)


class Movie(Base):
    __tablename__ = 'imdb_movies'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None]
    original_title: Mapped[str | None]
    url: Mapped[str | None] = mapped_column(index=True)

    # many-to-many relations
    genres: Mapped[list[Genre]] = relationship(secondary=genres_table, back_populates='movies')
    actors: Mapped[list[Actor]] = relationship(secondary=actors_table, back_populates='movies')
    directors: Mapped[list[Director]] = relationship(
        secondary=directors_table, back_populates='movies'
    )
    writers: Mapped[list[Writer]] = relationship(secondary=writers_table, back_populates='movies')
    plot_keywords: Mapped[list[PlotKeyword]] = relationship(
        secondary=plot_keywords_table, back_populates='movies'
    )
    languages: Mapped[list[MovieLanguage]] = relationship(order_by='MovieLanguage.prominence')

    score: Mapped[float | None]
    votes: Mapped[int | None]
    meta_score: Mapped[int | None]
    year: Mapped[int | None]
    plot_outline: Mapped[str | None]
    mpaa_rating: Mapped[str | None] = mapped_column(default='')
    photo: Mapped[str | None]

    # updated time, so we can grab new rating counts after 48 hours
    # set a default, so existing data gets updated with a rating
    updated: Mapped[datetime | None]

    @property
    def imdb_id(self):
        return extract_id(self.url)

    @property
    def expired(self):
        """:return: True if movie details are considered to be expired, ie. need of update"""
        if self.updated is None:
            logger.debug('updated is None: {}', self)
            return True
        refresh_interval = 2
        if self.year:
            # Make sure age is not negative
            age = max((datetime.now().year - self.year), 0)
            refresh_interval += age * 5
            logger.debug('movie `{}` age {} expires in {} days', self.title, age, refresh_interval)
        return self.updated < datetime.now() - timedelta(days=refresh_interval)

    def __repr__(self):
        return f'<Movie(name={self.title},votes={self.votes},year={self.year})>'


class MovieLanguage(Base):
    __tablename__ = 'imdb_movie_languages'

    movie_id: Mapped[int] = mapped_column(ForeignKey('imdb_movies.id'), primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey('imdb_languages.id'), primary_key=True)
    prominence: Mapped[int | None]

    language: Mapped[Language] = relationship()

    def __init__(self, language, prominence=None):
        self.language = language
        self.prominence = prominence


class Language(Base):
    __tablename__ = 'imdb_languages'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None]

    def __init__(self, name):
        self.name = name


class Genre(Base):
    __tablename__ = 'imdb_genres'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    movies: Mapped[list[Movie]] = relationship(secondary=genres_table, back_populates='genres')

    def __init__(self, name):
        self.name = name


class Actor(Base):
    __tablename__ = 'imdb_actors'

    id: Mapped[int] = mapped_column(primary_key=True)
    imdb_id: Mapped[str | None]
    name: Mapped[str | None]
    movies: Mapped[list[Movie]] = relationship(secondary=actors_table, back_populates='actors')

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class Director(Base):
    __tablename__ = 'imdb_directors'

    id: Mapped[int] = mapped_column(primary_key=True)
    imdb_id: Mapped[str | None]
    name: Mapped[str | None]
    movies: Mapped[list[Movie]] = relationship(
        secondary=directors_table, back_populates='directors'
    )

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class Writer(Base):
    __tablename__ = 'imdb_writers'

    id: Mapped[int] = mapped_column(primary_key=True)
    imdb_id: Mapped[str | None]
    name: Mapped[str | None]
    movies: Mapped[list[Movie]] = relationship(secondary=writers_table, back_populates='writers')

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class PlotKeyword(Base):
    __tablename__ = 'imdb_plot_keywords'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None]
    movies: Mapped[list[Movie]] = relationship(
        secondary=plot_keywords_table, back_populates='plot_keywords'
    )

    def __init__(self, name):
        self.name = name


class SearchResult(Base):
    __tablename__ = 'imdb_search'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(index=True)
    url: Mapped[str | None]
    fails: Mapped[bool | None] = mapped_column(default=False)
    queried: Mapped[datetime | None] = mapped_column(default=datetime.now)

    @property
    def imdb_id(self):
        return extract_id(self.url)

    def __init__(self, title, url=None):
        self.title = title
        self.url = url

    def __repr__(self):
        return f'<SearchResult(title={self.title},url={self.url},fails={self.fails})>'


@db_schema.upgrade('imdb_lookup')
def upgrade(ver, session):
    # v5  We may have cached bad data due to imdb changes, just wipe everything. GitHub #697
    # v6  The association tables were not cleared on the last upgrade, clear again. GitHub #714
    # v7  Another layout change cached bad data. GitHub #729
    # v8  Added writers to the DB Schema
    # v9  Added Metacritic score exftraction/filtering
    # v10 Added plot keywords to the DB schema
    if ver is None or ver <= 9:
        raise UpgradeImpossible(
            'Resetting imdb_lookup caches because bad data may have been cached.'
        )
    return ver
