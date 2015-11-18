from __future__ import unicode_literals, division, absolute_import

import logging
from datetime import datetime

from dateutil import parser
from pytvmaze import get_show
from pytvmaze.exceptions import ShowNotFound
from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, Numeric, PickleType, func, Table, and_, \
    or_
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.database import with_session
from flexget.utils.tools import split_title_year

log = logging.getLogger('api_tvmaze')

DB_VERSION = 0
Base = db_schema.versioned_base('tvmaze', DB_VERSION)
UPDATE_INTERVAL = 7  # Used for expiration, number is in days


class TVMazeGenre(Base):
    __tablename__ = 'tvmaze_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode, unique=True)


genres_table = Table('tvmaze_series_genres', Base.metadata,
                     Column('series_id', Integer, ForeignKey('tvmaze_series.maze_id')),
                     Column('genre_id', Integer, ForeignKey('tvmaze_genres.id')))


class TVMazeLookup(Base):
    __tablename__ = 'tvmaze_lookup'

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_name = Column(Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.maze_id'))
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
    webchannel = Column(String)
    runtime = Column(Integer)
    show_type = Column(String)
    network = Column(Unicode)
    seasons = relation('TVMazeSeasons', order_by='TVMazeSeasons.number', cascade='all, delete, delete-orphan',
                       backref='series')
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series, session):
        self.update(series, session)

    def update(self, series, session):
        self.status = series.status
        self.rating = series.rating['average']
        self.weight = series.weight
        self.updated = datetime.fromtimestamp(series.updated)
        self.name = series.name
        self.language = series.language
        self.schedule = series.schedule
        self.url = series.url
        self.image = series.image
        self.tvdb_id = series.externals.get('thetvdb')
        self.tvrage_id = series.externals.get('tvrage')
        self.premiered = parser.parse(series.premiered)
        self.summary = series.summary
        self.webchannel = series.webChannel
        self.runtime = series.runtime
        self.show_type = series.type
        self.maze_id = series.maze_id
        self.network = series.network['name']
        self.last_update = datetime.now()

        self.seasons[:] = get_db_season(self.maze_id, series.seasons, session)
        self.genres[:] = get_db_genres(series.genres, session)

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
    episodes = relation('TVMazeEpisodes', order_by='TVMazeEpisodes.season_number', cascade='all, delete, delete-orphan',
                        backref='season')
    last_update = Column(DateTime)

    def __init__(self, season, maze_id, session):
        super(TVMazeSeasons, self).__init__()
        self.update(season, maze_id, session)

    def update(self, season, maze_id, session):
        self.number = season.season_number
        self.series_maze_id = maze_id
        self.last_update = datetime.now()

        self.episodes[:] = get_db_episodes(self.id, season.episodes, session)


class TVMazeEpisodes(Base):
    __tablename__ = 'tvmaze_episode'

    maze_id = Column(Integer, primary_key=True)
    tvmaze_season_id = Column(Integer, ForeignKey('tvmaze_season.id'), nullable=False)
    title = Column(Unicode)
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
        self.maze_id = episode.maze_id
        self.tvmaze_season_id = season_id
        self.title = episode.title
        self.airdate = datetime.strptime(episode.airdate, '%Y-%m-%d')
        self.url = episode.url
        self.number = episode.episode_number
        self.season_number = episode.season_number
        self.image = episode.image.get('original', episode.image.get('medium'))
        self.airstamp = parser.parse(episode.airstamp)
        self.runtime = episode.runtime
        self.last_update = datetime.now()


def get_db_episodes(season_id, episodes, session):
    db_episodes = []
    for episode_num, episode in episodes.items():
        db_episode = session.query(TVMazeEpisodes).filter(TVMazeEpisodes.maze_id == episode.maze_id).first()
        if not db_episode:
            db_episode = TVMazeEpisodes(episode=episode, season_id=season_id)
            session.add(db_episode)
        db_episodes.append(db_episode)
    return db_episodes


def get_db_season(maze_id, seasons, session):
    db_seasons = []
    for season_num, season in seasons.items():
        db_season = session.query(TVMazeSeasons).filter(and_(
            TVMazeSeasons.series_maze_id == maze_id,
            TVMazeSeasons.number == season_num)).first()
        if not db_season:
            db_season = TVMazeSeasons(maze_id=maze_id, season=season, session=session)
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


def search_params_for_series(**lookup_params):
    search_params = {
        'maze_id': lookup_params.get('maze_id'),
        'tvdb_id': lookup_params.get('tvdb_id'),
        'tvrage_id': lookup_params.get('tvrage_id'),
        'name': lookup_params.get('title')
    }
    return search_params


@with_session
def from_cache(session=None, search_params=None, cache_type=None):
    """
    Returns a result from requested table based on search params
    :param session: Current session
    :param search_params: Relevant search params. Should match table column names
    :param cache_type: Object for search
    :return: Query result
    """
    result = None
    if not any(search_params.values()):
        raise LookupError('No parameters sent for lookup')
    else:
        result = session.query(cache_type).filter(
            or_(getattr(cache_type, col) == val for col, val in search_params.iteritems() if val)).first()
    return result


@with_session
def from_lookup(session=None, title=None):
    return session.query(TVMazeLookup).filter(func.lower(TVMazeLookup.search_name) == title.lower()).first()


def prepare_lookup(**lookup_params):
    """
    Return a dict of params which is valid with pytvmaze get_show method
    """
    prepared_params = {}
    series_name = lookup_params.get('series_name', lookup_params.get('show_name'))
    title, year_match = split_title_year(series_name)

    prepared_params['maze_id'] = lookup_params.get('tvmaze_id')
    prepared_params['tvdb_id'] = lookup_params.get('tvdb_id') or lookup_params.get('trakt_series_tvdb_id')
    prepared_params['tvrage_id'] = lookup_params.get('tvrage_id') or lookup_params.get('trakt_series_tvrage_id')
    prepared_params['show_name'] = title
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
        search_params = search_params_for_series(**lookup_params)
        # Searching cache first
        series = from_cache(session=session, cache_type=TVMazeSeries, search_params=search_params)

        # Preparing search from lookup table
        title = lookup_params.get('show_name')
        if not series and title:
            search = from_lookup(session=session, title=title)
            if search and search.series:
                series = search.series

        if force_cache:
            if series:  # If force_cache is True, return series even if it expired
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            return series

        prepared_params = prepare_lookup(**lookup_params)
        try:
            show = get_show(**prepared_params)
        except ShowNotFound:
            raise

        # See if series already exist in cache
        series = session.query(TVMazeSeries).filter(TVMazeSeries.maze_id == show.maze_id).first()
        if series:
            series.update(show, session)
        else:
            series = TVMazeSeries(show, session)
            session.add(series)

        # If there's a mismatch between actual series name and requested title,
        # add it to lookup table for future lookups
        if series and title.lower() != series.name.lower():
            session.add(TVMazeLookup(from_search=title, series=series))
        return series


@event('plugin.register')
def register_plugin():
    plugin.register(APITVMaze, 'api_tvmaze', api_ver=2)
