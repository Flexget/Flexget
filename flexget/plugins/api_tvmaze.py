from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime

from dateutil import parser
from pytvmaze import get_show, episode_by_number, episodes_by_date
from pytvmaze.exceptions import ShowNotFound, EpisodeNotFound, NoEpisodesForAirdate, IllegalAirDate, ConnectionError
from sqlalchemy import Column, Integer, Float, DateTime, String, Unicode, ForeignKey, func, Table, or_, \
    and_
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.database import with_session, json_synonym
from flexget.utils.tools import split_title_year, native_str_to_text

log = logging.getLogger('api_tvmaze')

DB_VERSION = 4
Base = db_schema.versioned_base('tvmaze', DB_VERSION)
UPDATE_INTERVAL = 7  # Used for expiration, number is in days


@db_schema.upgrade('tvmaze')
def upgrade(ver, session):
    if ver is None or ver < 4:
        raise db_schema.UpgradeImpossible
    return ver


actors_to_shows_table = Table('tvmaze_actors_to_shows', Base.metadata,
                              Column('series_id', Integer, ForeignKey('tvmaze_series.tvmaze_id')),
                              Column('actor_id', Integer, ForeignKey('tvmaze_actors.tvmaze_id')))
Base.register_table(actors_to_shows_table)


class TVMazeActor(Base):
    __tablename__ = 'tvmaze_actors'

    tvmaze_id = Column(Integer, primary_key=True)
    name = Column(Unicode, nullable=False)
    original_image = Column(String)
    medium_image = Column(String)
    url = Column(String)
    last_update = Column(DateTime)

    def to_dict(self):
        return {
            'tvmaze_id': self.tvmaze_id,
            'name': self.name,
            'original_image': self.original_image,
            'medium_image': self.medium_image,
            'url': self.url,
            'last_update': self.last_update
        }

    def __init__(self, actor):
        self.tvmaze_id = actor.id
        self.name = actor.name
        self.url = actor.url
        self.update(actor)

    def __repr__(self):
        return '<TVMazeActor,name={0},id={1}'.format(self.name, self.tvmaze_id)

    def update(self, actor):
        if actor.image:
            self.original_image = actor.image.get('original')
            self.medium_image = actor.image.get('medium')
        else:
            self.original_image = None
            self.medium_image = None
        self.last_update = datetime.now()

    @property
    def expired(self):
        if not self.last_update:
            log.debug('no last update attribute, actor set for update')
            return True
        time_dif = datetime.now() - self.last_update
        expiration = time_dif.days > UPDATE_INTERVAL
        return expiration


class TVMazeGenre(Base):
    __tablename__ = 'tvmaze_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode, unique=True)


genres_table = Table('tvmaze_series_genres', Base.metadata,
                     Column('series_id', Integer, ForeignKey('tvmaze_series.tvmaze_id')),
                     Column('genre_id', Integer, ForeignKey('tvmaze_genres.id')))

Base.register_table(genres_table)


class TVMazeLookup(Base):
    __tablename__ = 'tvmaze_lookup'

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_name = Column(Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.tvmaze_id'))
    series = relation('TVMazeSeries', backref='search_strings')

    def __repr__(self):
        return '<TVMazeLookup(search_name={0},series_id={1})'.format(self.search_name, self.series_id)


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
    _schedule = Column('schedule', Unicode)
    schedule = json_synonym('_schedule')
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
    actors = relation(TVMazeActor, secondary=actors_to_shows_table)
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series, session):
        self.tvmaze_id = series.maze_id
        self.update(series, session)

    def to_dict(self):
        return {
            'tvmaze_id': self.tvmaze_id,
            'status': self.status,
            'rating': self.rating,
            'genres': [genre.name for genre in self.genres],
            'weight': self.weight,
            'updated': self.updated,
            'name': self.name,
            'language': self.language,
            'schedule': self.schedule,
            'url': self.url,
            'original_image': self.original_image,
            'medium_image': self.medium_image,
            'tvdb_id': self.tvdb_id,
            'tvrage_id': self.tvrage_id,
            'premiered': self.premiered,
            'year': self.year,
            'summary': self.summary,
            'webchannel': self.webchannel,
            'runtime': self.runtime,
            'show_type': self.show_type,
            'network': self.network,
            'actors': [actor.to_dict() for actor in self.actors],
            'last_update': self.last_update
        }

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
            self.premiered = parser.parse(series.premiered, ignoretz=True)
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
        if series.cast and series.cast.people:
            self.actors[:] = get_db_actors(series.cast.people, session)
        else:
            self.actors[:] = []

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

    def to_dict(self):
        return {
            'tvmaze_id': self.tvmaze_id,
            'series_id': self.series_id,
            'number': self.number,
            'season_number': self.season_number,
            'title': self.title,
            'airdate': self.airdate,
            'url': self.url,
            'original_image': self.original_image,
            'medium_image': self.medium_image,
            'airstamp': self.airstamp,
            'runtime': self.runtime,
            'summary': self.summary,
            'last_update': self.last_update
        }

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
            self.airstamp = parser.parse(episode.airstamp, ignoretz=True)
        else:
            self.airstamp = None
        self.runtime = episode.runtime
        self.last_update = datetime.now()

    @property
    def expired(self):
        if not self.last_update:
            log.debug('no last update attribute, episode set for update')
            return True
        time_dif = datetime.now() - self.last_update
        expiration = time_dif.days > UPDATE_INTERVAL
        if expiration:
            log.debug('episode %s, season %s for series %s is expired.', self.number, self.season_number,
                      self.series_id)
        return expiration


def get_db_actors(actors, session):
    """
    Return a tuple of db actors list and db characters list generated from show cast.
    :param actors: List of actors retrieved by API
    :param session: DB Session
    :return: tuple of db actors list and db characters list
    """
    db_actors = []
    for actor in actors:
        db_actor = get_db_actor(actor, session)
        db_actors.append(db_actor)
    return db_actors


def get_db_actor(actor, session):
    db_actor = session.query(TVMazeActor).filter(TVMazeActor.tvmaze_id == actor.id).first()
    if not db_actor:
        db_actor = TVMazeActor(actor=actor)
        log.debug('adding actor %s to db', db_actor.name)
        session.add(db_actor)
    elif db_actor.expired:
        log.debug('found expired actor in db, refreshing')
        db_actor.update(actor)
    else:
        log.debug('actor %s found in db, returning', db_actor.name)
    return db_actor


def get_db_genres(genres, session):
    db_genres = []
    for genre in genres:
        db_genre = session.query(TVMazeGenre).filter(TVMazeGenre.name == genre).first()
        if not db_genre:
            db_genre = TVMazeGenre(name=genre)
            log.debug('adding genre %s to db', genre)
            session.add(db_genre)
        else:
            log.debug('genre %s found in db, returning', db_genre.name)
        db_genres.append(db_genre)
    return db_genres


def get_actor_details(actor):
    return {'name': actor.name,
            'original_image': actor.original_image,
            'medium_image': actor.medium_image,
            'url': actor.url,
            'id': actor.tvmaze_id
            }


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
        log.debug('searching db {0} for the values {1}'.format(cache_type.__tablename__, list(search_params.items())))
        result = session.query(cache_type).filter(
            or_(getattr(cache_type, col) == val for col, val in search_params.items() if val)).first()
    return result


@with_session
def from_lookup(session=None, title=None):
    log.debug('searching lookup table using title {0}'.format(title))
    return session.query(TVMazeLookup).filter(func.lower(TVMazeLookup.search_name) == title.lower()).first()


@with_session
def add_to_lookup(session=None, title=None, series=None):
    log.debug('trying to add search title {0} to series {1} in lookup table'.format(title, series.name))
    exist = session.query(TVMazeLookup).filter(TVMazeLookup.search_name == title).first()
    if exist:
        log.debug('title {0} already exist for series {1}, no need to save lookup'.format(title, series.name))
        return
    session.add(TVMazeLookup(search_name=title, series=series))


def prepare_lookup_for_pytvmaze(**lookup_params):
    """
    Return a dict of params which is valid with pytvmaze get_show method
    :param lookup_params: Search parameters
    :return: Dict of pytvmaze recognizable key words
    """
    prepared_params = {}
    title = None
    year_match = None
    series_name = lookup_params.get('series_name') or lookup_params.get('show_name') or lookup_params.get('title')
    if series_name:
        title, year_match = split_title_year(series_name)
    # Support for when title is just a number
    if not title:
        title = series_name

    network = lookup_params.get('network') or lookup_params.get('trakt_series_network')
    country = lookup_params.get('country') or lookup_params.get('trakt_series_country')
    language = lookup_params.get('language')

    prepared_params['maze_id'] = lookup_params.get('tvmaze_id')
    prepared_params['tvdb_id'] = lookup_params.get('tvdb_id') or lookup_params.get('trakt_series_tvdb_id')
    prepared_params['tvrage_id'] = lookup_params.get('tvrage_id') or lookup_params.get('trakt_series_tvrage_id')
    prepared_params['imdb_id'] = lookup_params.get('imdb_id')
    prepared_params['show_name'] = native_str_to_text(title, encoding='utf-8') if title else None
    prepared_params['show_year'] = lookup_params.get('trakt_series_year') or lookup_params.get(
        'year') or lookup_params.get('imdb_year') or year_match

    prepared_params['show_network'] = native_str_to_text(network, encoding='utf8') if network else None
    prepared_params['show_country'] = native_str_to_text(country, encoding='utf8') if country else None
    prepared_params['show_language'] = native_str_to_text(language, encoding='utf8') if language else None

    # Include cast information by default
    prepared_params['embed'] = 'cast'

    return prepared_params


class APITVMaze(object):
    @staticmethod
    @with_session
    def series_lookup(session=None, only_cached=False, **lookup_params):
        search_params = search_params_for_series(**lookup_params)
        # Searching cache first
        series = from_cache(session=session, cache_type=TVMazeSeries, search_params=search_params)

        search = None
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
            raise LookupError(e.value)
        except ConnectionError as e:
            log.warning(e)
            raise LookupError(e.value)

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

        # Check if show returned from lookup table as expired. Relevant only if search by title
        if title:
            if series and title.lower() == series.name.lower():
                return series
            elif series and not search:
                log.debug('mismatch between search title {0} and series title {1}. '
                          'saving in lookup table'.format(title, series.name))
                add_to_lookup(session=session, title=title, series=series)
            elif series and search:
                log.debug('Updating search result in db')
                search.series = series
        return series

    @staticmethod
    @with_session
    def episode_lookup(session=None, only_cached=False, **lookup_params):
        series_name = lookup_params.get('series_name') or lookup_params.get('title')
        show_id = lookup_params.get('tvmaze_id') or lookup_params.get('tvdb_id')
        lookup_type = lookup_params.get('series_id_type')

        season_number = lookup_params.get('series_season')
        episode_number = lookup_params.get('series_episode')

        episode_date = lookup_params.get('series_date')

        # Verify we have enough parameters for search
        if not any([series_name, show_id]):
            raise LookupError('Not enough parameters to lookup episode')
        if lookup_type == 'ep' and not all([season_number, episode_number]):
            raise LookupError('Not enough parameters to lookup episode')
        elif lookup_type == 'date' and not episode_date:
            raise LookupError('Not enough parameters to lookup episode')

        # Get series
        series = APITVMaze.series_lookup(session=session, only_cached=only_cached, **lookup_params)
        if not series:
            raise LookupError('Could not find series with the following parameters: {0}'.format(lookup_params))

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
                log.debug('forcing cache for episode id {3}, number{0}, season {1} for show {2}'
                          .format(episode.number,
                                  episode.season_number,
                                  series.name,
                                  episode.tvmaze_id))
                return episode
        if episode and not episode.expired:
            log.debug('found episode id {3}, number {0}, season {1} for show {2} in cache'
                      .format(episode.number,
                              episode.season_number,
                              series.name,
                              episode.tvmaze_id))

            return episode

        # Lookup episode via its type (number or airdate)
        if lookup_type == 'date':
            try:
                episode_date = datetime.strftime(episode_date, '%Y-%m-%d')
                pytvmaze_episode = episodes_by_date(maze_id=series.tvmaze_id, airdate=episode_date)[0]
            except (IllegalAirDate, NoEpisodesForAirdate) as e:
                log.debug(e)
                raise LookupError(e.value)
            except ConnectionError as e:
                log.warning(e)
                raise LookupError(e.value)
        else:
            # TODO will this match all series_id types?
            try:
                log.debug(
                    'fetching episode {0} season {1} for series_id {2} for tvmaze'.format(episode_number,
                                                                                          season_number,
                                                                                          series.tvmaze_id))
                pytvmaze_episode = episode_by_number(maze_id=series.tvmaze_id, season_number=season_number,
                                                     episode_number=episode_number)
            except EpisodeNotFound as e:
                log.debug('could not find episode in tvmaze: {0}'.format(e))
                raise LookupError(e.value)
            except ConnectionError as e:
                log.warning(e)
                raise LookupError(e.value)
        # See if episode exists in DB
        episode = session.query(TVMazeEpisodes).filter(
            or_(TVMazeEpisodes.tvmaze_id == pytvmaze_episode.maze_id,
                and_(
                    TVMazeEpisodes.number == pytvmaze_episode.episode_number,
                    TVMazeEpisodes.season_number == pytvmaze_episode.season_number)
                )
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
