from __future__ import unicode_literals, division, absolute_import

import logging
from datetime import datetime

from dateutil import parser
from pytvmaze import get_show, episode_by_number, episodes_by_date
from pytvmaze.exceptions import ShowNotFound, EpisodeNotFound, NoEpisodesForAirdate, IllegalAirDate, ConnectionError
from sqlalchemy import Column, Integer, Float, DateTime, String, Unicode, ForeignKey, Numeric, PickleType, func, Table, or_, \
    and_
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.database import with_session
from flexget.utils.tools import split_title_year

log = logging.getLogger('api_tvmaze')

DB_VERSION = 1
Base = db_schema.versioned_base('tvmaze', DB_VERSION)
UPDATE_INTERVAL = 7  # Used for expiration, number is in days


@db_schema.upgrade('tvmaze')
def upgrade(ver, session):
    if ver == 0:
        raise db_schema.UpgradeImpossible
    return ver


class TVMazeGenre(Base):
    __tablename__ = 'tvmaze_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode, unique=True)


genres_table = Table('tvmaze_series_genres', Base.metadata,
                     Column('series_id', Integer, ForeignKey('tvmaze_series.tvmaze_id')),
                     Column('genre_id', Integer, ForeignKey('tvmaze_genres.id')))


class TVMazeLookup(Base):
    __tablename__ = 'tvmaze_lookup'

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_name = Column(Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.tvmaze_id'))
    series = relation('TVMazeSeries', backref='search_strings')


class TVMazeSeries(Base):
    __tablename__ = 'tvmaze_series'

    tvmaze_id = Column(Integer, primary_key=True)
    status = Column(Unicode)
    rating = Column(Float)
    genres = relation(TVMazeGenre, secondary=genres_table)
    weight = Column(Integer)
    updated = Column(DateTime)  # last time show was updated at tvmaze
    name = Column(Unicode)
    language = Column(Unicode)
    schedule = Column(PickleType)
    url = Column(String)
    original_image = Column(String)
    medium_image = Column(String)
    tvdb_id = Column(Integer)
    tvrage_id = Column(Integer)
    premiered = Column(DateTime)
    year = Column(Integer)
    summary = Column(Unicode)
    webchannel = Column(String)
    runtime = Column(Integer)
    show_type = Column(String)
    network = Column(Unicode)
    episodes = relation('TVMazeEpisodes', order_by='TVMazeEpisodes.season_number', cascade='all, delete, delete-orphan',
                        backref='series')
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series, session):
        self.tvmaze_id = series.maze_id
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
        if series.image:
            self.original_image = series.image.get('original')
            self.medium_image = series.image.get('medium')
        else:
            self.original_image = None
            self.medium_image = None
        self.tvdb_id = series.externals.get('thetvdb')
        self.tvrage_id = series.externals.get('tvrage')
        if series.premiered:
            self.premiered = parser.parse(series.premiered)
            self.year = int(series.premiered[:4])
        else:
            self.premiered = None
            self.year = None
        self.summary = series.summary
        if series.web_channel:
            self.webchannel = series.web_channel.get('name')
        else:
            self.webchannel = None
        self.runtime = series.runtime
        self.show_type = series.type
        if series.network:
            self.network = series.network.get('name')
        else:
            self.network = None
        self.last_update = datetime.now()

        self.genres[:] = get_db_genres(series.genres, session)

    def __repr__(self):
        return '<TVMazeSeries(title=%s,id=%s,last_update=%s)>' % (self.name, self.tvmaze_id, self.last_update)

    def __str__(self):
        return self.name

    @property
    def expired(self):
        if not self.last_update:
            log.debug('no last update attribute, series set for update')
            return True
        time_dif = datetime.now() - self.last_update
        expiration = time_dif.days > UPDATE_INTERVAL
        log.debug('series {0} is expired: {1}'.format(self.name, expiration))
        return expiration


class TVMazeEpisodes(Base):
    __tablename__ = 'tvmaze_episode'

    tvmaze_id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.tvmaze_id'), nullable=False)
    number = Column(Integer, nullable=False)
    season_number = Column(Integer, nullable=False)

    title = Column(Unicode)
    airdate = Column(DateTime)
    url = Column(String)
    original_image = Column(String)
    medium_image = Column(String)
    airstamp = Column(DateTime)
    runtime = Column(Integer)
    summary = Column(Unicode)
    last_update = Column(DateTime)

    def __init__(self, episode, series_id):
        self.series_id = series_id
        self.tvmaze_id = episode.maze_id
        self.season_number = episode.season_number
        self.number = episode.episode_number
        self.update(episode)

    def update(self, episode):
        self.summary = episode.summary
        self.title = episode.title
        if episode.airdate:
            self.airdate = datetime.strptime(episode.airdate, '%Y-%m-%d')
        else:
            self.airdate = None
        self.url = episode.url
        if episode.image:
            self.original_image = episode.image.get('original')
            self.medium_image = episode.image.get('medium')
        else:
            self.original_image = None
            self.medium_image = None
        if episode.airstamp:
            self.airstamp = parser.parse(episode.airstamp)
        else:
            self.airstamp = None
        self.runtime = episode.runtime
        self.last_update = datetime.now()

    @property
    def expired(self):
        if not self.last_update:
            log.debug('no last update attribute, series set for update')
            return True
        time_dif = datetime.now() - self.last_update
        expiration = time_dif.days > UPDATE_INTERVAL
        log.debug('episode {0}, season {1} for series {2} is expired.'
                  'days overdue for update: {3}'.format(self.number, self.season_number, self.series_id, expiration))
        return expiration


def get_db_genres(genres, session):
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
        'tvmaze_id': lookup_params.get('maze_id') or lookup_params.get('tvmaze_id'),
        'tvdb_id': lookup_params.get('tvdb_id'),
        'tvrage_id': lookup_params.get('tvrage_id'),
        'name': lookup_params.get('title') or lookup_params.get('series_name')
    }
    log.debug('returning search params for series lookup: {0}'.format(search_params))
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
    if not any(search_params.values()):
        raise LookupError('No parameters sent for cache lookup')
    else:
        log.debug('searching db {0} for the values {1}'.format(cache_type.__tablename__, search_params.items()))
        result = session.query(cache_type).filter(
            or_(getattr(cache_type, col) == val for col, val in search_params.iteritems() if val)).first()
    return result


@with_session
def from_lookup(session=None, title=None):
    log.debug('searching lookup table using title {0}'.format(title))
    return session.query(TVMazeLookup).filter(func.lower(TVMazeLookup.search_name) == title.lower()).first()


def prepare_lookup_for_pytvmaze(**lookup_params):
    """
    Return a dict of params which is valid with pytvmaze get_show method
    :param lookup_params: Search parameters
    :return: Dict of pytvmaze recognizable key words
    """
    prepared_params = {}
    series_name = lookup_params.get('series_name') or lookup_params.get('show_name') or lookup_params.get('title')
    title, year_match = split_title_year(series_name)
    # Support for when title is just a number
    if not title:
        title = series_name

    prepared_params['maze_id'] = lookup_params.get('tvmaze_id')
    prepared_params['tvdb_id'] = lookup_params.get('tvdb_id') or lookup_params.get('trakt_series_tvdb_id')
    prepared_params['tvrage_id'] = lookup_params.get('tvrage_id') or lookup_params.get('trakt_series_tvrage_id')
    prepared_params['show_name'] = title
    prepared_params['show_year'] = lookup_params.get('trakt_series_year') or lookup_params.get(
        'year') or lookup_params.get('imdb_year') or year_match
    prepared_params['show_network'] = lookup_params.get('network') or lookup_params.get('trakt_series_network')
    prepared_params['show_country'] = lookup_params.get('country') or lookup_params.get('trakt_series_country')
    prepared_params['show_language'] = lookup_params.get('language')

    return prepared_params


class APITVMaze(object):
    @staticmethod
    @with_session
    def series_lookup(session=None, only_cached=False, **lookup_params):
        search_params = search_params_for_series(**lookup_params)
        # Searching cache first
        series = from_cache(session=session, cache_type=TVMazeSeries, search_params=search_params)

        # Preparing search from lookup table
        title = lookup_params.get('series_name') or lookup_params.get('show_name') or lookup_params.get('title')
        if not series and title:
            log.debug('did not find exact match for series {0} in cache, looking in search table'.format(
                search_params['name']))
            search = from_lookup(session=session, title=title)
            if search and search.series:
                series = search.series
                log.debug('found series {0} from search table'.format(series.name))

        if only_cached:
            if series:  # If force_cache is True, return series even if it expired
                log.debug('forcing cache for series {0}'.format(series.name))
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            log.debug('returning series {0} from cache'.format(series.name))
            return series

        prepared_params = prepare_lookup_for_pytvmaze(**lookup_params)
        try:
            log.debug('trying to fetch series {0} from pytvmaze'.format(title))
            pytvmaze_show = get_show(**prepared_params)
        except ShowNotFound as e:
            log.debug('could not find series {0} in pytvmaze'.format(title))
            raise LookupError(e)
        except ConnectionError as e:
            log.warning(e)
            raise LookupError(e)

        # See if series already exist in cache
        series = session.query(TVMazeSeries).filter(TVMazeSeries.tvmaze_id == pytvmaze_show.maze_id).first()
        if series:
            log.debug('series {0} is already in cache, checking for expiration'.format(series.name))
            if series.expired:
                series.update(pytvmaze_show, session)
        else:
            log.debug('creating new series {0} in tvmaze_series db'.format(pytvmaze_show.name))
            series = TVMazeSeries(pytvmaze_show, session)
            session.add(series)
        # If there's a mismatch between actual series name and requested title,
        # add it to lookup table for future lookups
        if series and title.lower() != series.name.lower():
            log.debug('mismatch between series title {0} and search title {1}. '
                      'saving in lookup table'.format(title, series.name))
            session.add(TVMazeLookup(search_name=title, series=series))
        return series

    @staticmethod
    @with_session
    def episode_lookup(session=None, only_cached=False, **lookup_params):
        series_name = lookup_params.get('series_name') or lookup_params.get('title')
        lookup_type = lookup_params.get('series_id_type')

        season_number = lookup_params.get('series_season')
        episode_number = lookup_params.get('series_episode')

        episode_date = lookup_params.get('series_date')

        # Verify we have enough parameters for search
        if lookup_type == 'ep' and not all([season_number, episode_number, series_name]):
            raise LookupError('Not enough parameters to lookup episode')
        elif lookup_type == 'date' and not all([series_name, episode_date]):
            raise LookupError('Not enough parameters to lookup episode')

        # Get series
        series = APITVMaze.series_lookup(session=session, only_cached=only_cached, **lookup_params)
        if not series:
            raise LookupError('Could not find series with the following parameters: {0}'.format(**lookup_params))

        # See if episode already exists in cache
        log.debug('searching for episode of show {0} in cache'.format(series.name))
        episode = session.query(TVMazeEpisodes).filter(
            or_(
                and_(TVMazeEpisodes.series_id == series.tvmaze_id,
                     TVMazeEpisodes.season_number == season_number,
                     TVMazeEpisodes.number == episode_number),
                and_(TVMazeEpisodes.series_id == series.tvmaze_id,
                     TVMazeEpisodes.airdate == episode_date)
            )
        ).first()

        # Logic for cache only mode
        if only_cached:
            if episode:
                log.debug('forcing cache for episode {0}, season {1} for show {2}'.format(episode.number,
                                                                                          episode.season_number,
                                                                                          series.name))
                return episode
        if episode and not episode.expired:
            log.debug('found episode {0}, season {1} for show {2} in cache'.format(episode.number,
                                                                                   episode.season_number,
                                                                                   series.name))

            return episode

        # Lookup episode via its type (number or airdate)
        if lookup_type == 'date':
            try:
                episode_date = datetime.strftime(episode_date, '%Y-%m-%d')
                pytvmaze_episode = episodes_by_date(maze_id=series.tvmaze_id, airdate=episode_date)[0]
            except (IllegalAirDate, NoEpisodesForAirdate) as e:
                log.debug(e)
                raise LookupError(e)
            except ConnectionError as e:
                log.warning(e)
                raise LookupError(e)
        else:
            # TODO will this match all series_id types?
            try:
                log.debug(
                    'fetching episode {0} season {1} for series_id {2} for tvmaze'.format(episode_number, season_number,
                                                                                          series.tvmaze_id))
                pytvmaze_episode = episode_by_number(maze_id=series.tvmaze_id, season_number=season_number,
                                                     episode_number=episode_number)
            except EpisodeNotFound as e:
                log.debug('could not find episode in tvmaze: {0}'.format(e))
                raise LookupError(e)
            except ConnectionError as e:
                log.warning(e)
                raise LookupError(e)
        # See if episode exists in DB
        episode = session.query(TVMazeEpisodes).filter(
            and_(
                TVMazeEpisodes.tvmaze_id == pytvmaze_episode.maze_id,
                TVMazeEpisodes.number == pytvmaze_episode.episode_number,
                TVMazeEpisodes.season_number == pytvmaze_episode.season_number)
        ).first()

        if episode:
            log.debug('found expired episode {0} in cache, refreshing data.'.format(episode.tvmaze_id))
            episode.update(pytvmaze_episode)
        else:
            log.debug('creating new episode for show {0}'.format(series.name))
            episode = TVMazeEpisodes(pytvmaze_episode, series.tvmaze_id)
            session.add(episode)

        return episode


@event('plugin.register')
def register_plugin():
    plugin.register(APITVMaze, 'api_tvmaze', api_ver=2)
