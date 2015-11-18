from __future__ import unicode_literals, division, absolute_import

import logging
import re
from datetime import datetime

from pytvmaze import get_show
from pytvmaze.exceptions import ShowNotFound
from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, Numeric, PickleType, func, Table, and_
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.database import with_session

log = logging.getLogger('api_tvmaze')

DB_VERSION = 0
Base = db_schema.versioned_base('tvmaze', DB_VERSION)
UPDATE_INTERVAL = 7  # Used for expiration, number is in days


class TVMazeGenre(Base):
    __tablename__ = 'tvmaze_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode, unique=True)


genres_table = Table('tvmaze_series_genres', Base.metadata,
                     Column('series_id', Integer, ForeignKey('tvmaze_series.id')),
                     Column('genre_id', Integer, ForeignKey('tvmaze_genres.id')))


class TVMazeLookup(Base):
    __tablename__ = 'tvmaze_lookup'

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_name = Column(Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.id'))
    series = relation('TVMazeSeries', backref='search_strings')


class TVMazeSeries(Base):
    __tablename__ = 'tvmaze_series'

    maze_id = Column(Integer, primary_key=True)
    status = Column(Unicode)
    rating = Column(Numeric)
    genres = relation(TVMazeGenre, secondary=genres_table)
    weight = Column(Integer)
    updated = Column(DateTime)  # last time show was updated at tvmaze
    name = Column(Unicode)
    language = Column(Unicode)
    schedule = Column(PickleType)
    url = Column(String)
    image = Column(PickleType)
    tvdb_id = Column(Integer)
    tvrage_id = Column(Integer)
    premiered = Column(DateTime)
    summary = Column(Unicode)
    webChannel = Column(String)
    runtime = Column(Integer)
    show_type = Column(String)
    network = Column(Unicode)
    seasons = relation('TVMazeSeasons', order_by='TVMazeSeasons.number', cascade='all, delete, delete-orphan',
                       backref='series')
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series, session):
        self.update(series, session)

    def update(self, series, session):
        self.status = series['status']
        self.rating = series['rating']['average']
        self.weight = series['weight']
        self.updated = datetime.fromtimestamp(series['updated']).strftime('%Y-%m-%d %H:%M:%S')
        self.name = series['name']
        self.language = series['language']
        self.schedule = series['scheduele']
        self.url = series['url']
        self.image = series['image']
        self.tvdb_id = series['externals'].get('thetvdb')
        self.tvrage_id = series['externals'].get('tvrage')
        self.premiered = series['premiered']
        self.summary = series['summary']
        self.webChannel = series.get('webChannel')
        self.runtime = series['runtime']
        self.show_type = series['type']
        self.maze_id = series['maze_id']
        self.network = series.network['name']
        self.last_update = datetime.now()

        self.seasons[:] = get_db_season(self.maze_id, series['seasons'], session)
        self.genres[:] = get_db_genres(series.get('genres', []), session)

    def __repr__(self):
        return '<TVMazeSeries(title=%s,id=%s,last_update=%s)>' % (self.name, self.id, self.last_update)

    def __str__(self):
        return self.name

    @property
    def expired(self):
        if not self.last_update:
            return True
        time_dif = datetime.now() - self.last_update
        return time_dif.days > UPDATE_INTERVAL


class TVMazeSeasons(Base):
    __tablename__ = 'tvmaze_season'

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_maze_id = Column(Integer, ForeignKey('tvmaze_series.maze_id'), nullable=False)
    number = Column(Integer)
    episodes = relation('TVMazeEpisodes', order_by='TVMazeEpisodes.season', cascade='all, delete, delete-orphan',
                        backref='season')
    last_update = Column(DateTime)

    def __init__(self, season, maze_id, session):
        self.update(season, maze_id, session)

    def update(self, season, maze_id, session):
        self.number = season['season_number']
        self.series_maze_id = maze_id
        self.last_update = datetime.now()

        self.episodes[:] = get_db_episodes(self.id, season['episodes'], session)


class TVMazeEpisodes(Base):
    __tablename__ = 'tvmaze_epiosde'

    maze_id = Column(Integer, primary_key=True)
    tvmaze_season_id = Column(Integer, ForeignKey('tvmaze_season.id'), nullable=False)
    name = Column(Unicode)
    airdate = Column(DateTime)
    url = Column(String)
    number = Column(Integer)
    season_number = Column(Integer)
    image = Column(String)
    airstamp = Column(DateTime)
    runtime = Column(Integer)
    last_update = Column(DateTime)

    def __init__(self, episode, season_id):
        self.update(episode, season_id)

    def update(self, episode, season_id):
        self.maze_id = episode['maze_id']
        self.tvmaze_season_id = season_id
        self.name = episode['name']
        self.airdate = datetime.strptime(episode.airdate, '%Y-%m-%d')
        self.url = episode['url']
        self.number = episode['episode_number']
        self.season_number = episode['season_number']
        self.image = episode['image']
        self.airstamp = datetime.strptime(episode.airstamp, '%Y-%m-%dT%H:%M:%S%z')
        self.runtime = episode['runtime']
        self.last_update = datetime.now()


def get_db_episodes(season_id, episodes, session):
    db_episodes = []
    for episode in episodes:
        db_episode = session.query(TVMazeEpisodes).filter(TVMazeEpisodes.maze_id == episode['maze_id']).first()
        if not db_episode:
            db_episode = TVMazeEpisodes(episode, season_id)
            session.add(db_episode)
        db_episodes.append(db_episode)
    return db_episodes

def get_db_season(maze_id, seasons, session):
    db_seasons = []
    for season in seasons:
        db_season = session.query(TVMazeSeasons).filter(and_(
            TVMazeSeasons.tvmaze_series_id == maze_id,
            TVMazeSeasons.number == season['season_number'])).first()
        if not db_season:
            db_season = TVMazeSeasons(maze_id, season)
            session.add(db_season)
        db_seasons.append(db_season)
    return db_seasons


def get_db_genres(genres, session):
    """Takes a list of genres as strings, returns the database instances for them."""
    db_genres = []
    for genre in genres:
        db_genre = session.query(TVMazeGenre).filter(TVMazeGenre.name == genre).first()
        if not db_genre:
            db_genre = TVMazeGenre(name=genre)
            session.add(db_genre)
        db_genres.append(db_genre)
    return db_genres


@with_session
def from_cache(session=None, **lookup_params):
    if not any(
            [lookup_params['maze_id'], lookup_params['tvdb_id'], lookup_params['tvrage_id'], lookup_params['title']]):
        raise LookupError('No parameters sent for TVMaze series lookup')
    series = None
    if lookup_params['maze_id']:
        series = session.query(TVMazeSeries).filter(TVMazeSeries.maze_id == lookup_params['maze_id']).first()
    elif lookup_params['tvdb_id']:
        series = session.query(TVMazeSeries).filter(TVMazeSeries.tvdb_id == lookup_params['tvdb_id']).first()
    elif lookup_params['tvrage_id']:
        series = session.query(TVMazeSeries).filter(TVMazeSeries.tvrage_id == lookup_params['tvrage_id']).first()
    if not series and lookup_params['title']:
        series = session.query(TVMazeSeries).filter(TVMazeSeries.name == lookup_params['title'].lower()).first()
    if series:
        return series


@with_session
def from_search(session=None, title=None):
    return session.query(TVMazeLookup).filter(func.lower(TVMazeLookup.search_name) == title.lower()).first()


def prepare_lookup(**lookup_params):
    prepared_params = {}
    series_name = lookup_params['series_name']
    season = lookup_params['series_season']
    episode_number = lookup_params['series_episode']
    year_match = re.search('\(([\d]{4})\)', series_name)  # Gets year from title if present
    if year_match:
        year_match = year_match.group(1)

    prepared_params['maze_id'] = lookup_params.get('tvmaze_id')
    prepared_params['tvdb_id'] = lookup_params.get('tvdb_id') or lookup_params.get('trakt_series_tvdb_id')
    prepared_params['tvrage_id'] = lookup_params.get('tvrage_id') or lookup_params.get('trakt_series_tvrage_id')
    prepared_params['show_name'] = re.sub('\(([\d]{4})\)', '', series_name).rstrip()  # Remove year from name if present
    prepared_params['show_year'] = lookup_params.get('trakt_series_year') or lookup_params.get('year') or \
                                   lookup_params.get('imdb_year') or year_match
    prepared_params['show_network'] = lookup_params.get('network') or lookup_params.get('trakt_series_network')
    prepared_params['show_country'] = lookup_params.get('country') or lookup_params.get('trakt_series_country')
    prepared_params['show_language'] = lookup_params.get('language')

    return prepared_params


class APITVMaze(object):
    @staticmethod
    @with_session
    def series_lookup(session=None, force_cache=False, **lookup_params):
        series = from_cache(session=session, **lookup_params)
        if force_cache:
            if series:
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            return series
        title = lookup_params.get('title')
        if title:
            search = from_search(session=session, title=title)
            if search and search.series:
                return search.series
        prepared_params = prepare_lookup(**lookup_params)
        try:
            series = get_show(**prepared_params)
        except ShowNotFound:
            raise LookupError('Show was not found on TVMaze')
        series = TVMazeSeries(series, session)
        session.add(series)
        session.add(TVMazeLookup(from_search=title, series=series))
        return series


@event('plugin.register')
def register_plugin():
    plugin.register(APITVMaze, 'api_tvmaze', api_ver=2)
