from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Table, Unicode
from sqlalchemy.orm import relation
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
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('imdb_genres.id')),
    Index('ix_imdb_movie_genres', 'movie_id', 'genre_id'),
)
Base.register_table(genres_table)

actors_table = Table(
    'imdb_movie_actors',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('actor_id', Integer, ForeignKey('imdb_actors.id')),
    Index('ix_imdb_movie_actors', 'movie_id', 'actor_id'),
)
Base.register_table(actors_table)

directors_table = Table(
    'imdb_movie_directors',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('director_id', Integer, ForeignKey('imdb_directors.id')),
    Index('ix_imdb_movie_directors', 'movie_id', 'director_id'),
)
Base.register_table(directors_table)

writers_table = Table(
    'imdb_movie_writers',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('writer_id', Integer, ForeignKey('imdb_writers.id')),
    Index('ix_imdb_movie_writers', 'movie_id', 'writer_id'),
)
Base.register_table(writers_table)

plot_keywords_table = Table(
    'imdb_movie_plot_keywords',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('keyword_id', Integer, ForeignKey('imdb_plot_keywords.id')),
    Index('ix_imdb_movie_plot_keywords', 'movie_id', 'keyword_id'),
)
Base.register_table(plot_keywords_table)


class Movie(Base):
    __tablename__ = 'imdb_movies'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    original_title = Column(Unicode)
    url = Column(String, index=True)

    # many-to-many relations
    genres = relation('Genre', secondary=genres_table, backref='movies')
    actors = relation('Actor', secondary=actors_table, backref='movies')
    directors = relation('Director', secondary=directors_table, backref='movies')
    writers = relation('Writer', secondary=writers_table, backref='movies')
    plot_keywords = relation('PlotKeyword', secondary=plot_keywords_table, backref='movies')
    languages = relation('MovieLanguage', order_by='MovieLanguage.prominence')

    score = Column(Float)
    votes = Column(Integer)
    meta_score = Column(Integer)
    year = Column(Integer)
    plot_outline = Column(Unicode)
    mpaa_rating = Column(String, default='')
    photo = Column(String)

    # updated time, so we can grab new rating counts after 48 hours
    # set a default, so existing data gets updated with a rating
    updated = Column(DateTime)

    @property
    def imdb_id(self):
        return extract_id(self.url)

    @property
    def expired(self):
        """
        :return: True if movie details are considered to be expired, ie. need of update
        """
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

    movie_id = Column(Integer, ForeignKey('imdb_movies.id'), primary_key=True)
    language_id = Column(Integer, ForeignKey('imdb_languages.id'), primary_key=True)
    prominence = Column(Integer)

    language = relation('Language')

    def __init__(self, language, prominence=None):
        self.language = language
        self.prominence = prominence


class Language(Base):
    __tablename__ = 'imdb_languages'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    def __init__(self, name):
        self.name = name


class Genre(Base):
    __tablename__ = 'imdb_genres'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name


class Actor(Base):
    __tablename__ = 'imdb_actors'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(Unicode)

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class Director(Base):
    __tablename__ = 'imdb_directors'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(Unicode)

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class Writer(Base):
    __tablename__ = 'imdb_writers'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(Unicode)

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class PlotKeyword(Base):
    __tablename__ = "imdb_plot_keywords"

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name


class SearchResult(Base):
    __tablename__ = 'imdb_search'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    url = Column(String)
    fails = Column(Boolean, default=False)
    queried = Column(DateTime)

    @property
    def imdb_id(self):
        return extract_id(self.url)

    def __init__(self, title, url=None):
        self.title = title
        self.url = url
        self.queried = datetime.now()

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
