from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime, timedelta

from dateutil import parser
from future.utils import native
from requests.exceptions import RequestException
from sqlalchemy import Column, Integer, Float, DateTime, String, Unicode, ForeignKey, Table, or_, \
    and_
from sqlalchemy.orm import relation
from sqlalchemy.orm.exc import MultipleResultsFound

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils import requests
from flexget.utils.database import with_session, json_synonym
from flexget.utils.tools import split_title_year

log = logging.getLogger('api_tvmaze')

DB_VERSION = 6
Base = db_schema.versioned_base('tvmaze', DB_VERSION)
UPDATE_INTERVAL = 7  # Used for expiration, number is in days
BASE_URL = 'http://api.tvmaze.com'

TVMAZE_ENDPOINTS = {
    'tvmaze_id': '/shows/{}',
    'imdb_id': '/lookup/shows?imdb={}',
    'tvrage_id': '/lookup/shows?tvrage={}',
    'thetvdb_id': '/lookup/shows?thetvdb={}',
    'show_name': '/singlesearch/shows?q={}',
    'date': '/shows/{}/episodesbydate?date={}',
    'number': '/shows/{}/episodebynumber?season={}&number={}'
}


@db_schema.upgrade('tvmaze')
def upgrade(ver, session):
    if ver is None or ver < 6:
        raise db_schema.UpgradeImpossible
    return ver


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

    def __init__(self, search_name, series_id=None, series=None):
        self.search_name = search_name.lower()
        if series_id:
            self.series_id = series_id
        if series:
            self.series = series

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
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series, session):
        self.tvmaze_id = series['id']
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
            'last_update': self.last_update
        }

    def update(self, series, session):
        self.status = series['status']
        self.rating = series['rating']['average']
        self.weight = series['weight']
        self.updated = datetime.fromtimestamp(series['updated'])
        self.name = series['name']
        self.language = series['language']
        self.schedule = series['schedule']
        self.url = series['url']
        self.original_image = series.get('image').get('original') if series.get('image') else None
        self.medium_image = series.get('image').get('medium') if series.get('image') else None
        self.tvdb_id = series['externals'].get('thetvdb')
        self.tvrage_id = series['externals'].get('tvrage')
        self.premiered = parser.parse(series.get('premiered'), ignoretz=True) if series.get('premiered') else None
        self.year = int(series.get('premiered')[:4]) if series.get('premiered') else None
        self.summary = series['summary']
        self.webchannel = series.get('web_channel')['name'] if series.get('web_channel') else None
        self.runtime = series['runtime']
        self.show_type = series['type']
        self.network = series.get('network')['name'] if series.get('network') else None
        self.last_update = datetime.now()

        self.genres[:] = get_db_genres(series['genres'], session)

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
        self.tvmaze_id = episode['id']
        self.season_number = episode['season']
        self.number = episode['number']
        self.update(episode)

    def update(self, episode):
        self.summary = episode['summary']
        self.title = episode['name']
        self.airdate = datetime.strptime(episode.get('airdate'), '%Y-%m-%d') if episode.get('airdate') else None
        self.url = episode['url']
        self.original_image = episode.get('image').get('original') if episode.get('image') else None
        self.medium_image = episode.get('image').get('medium') if episode.get('image') else None
        self.airstamp = parser.parse(episode.get('airstamp'), ignoretz=True) if episode.get('airstamp') else None
        self.runtime = episode['runtime']
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


def get_db_genres(genres, session):
    db_genres = []
    for genre in genres:
        db_genre = session.query(TVMazeGenre).filter(TVMazeGenre.name == genre).first()
        if not db_genre:
            db_genre = TVMazeGenre(name=genre)
            log.trace('adding genre %s to db', genre)
            session.add(db_genre)
        else:
            log.trace('genre %s found in db, returning', db_genre.name)
        db_genres.append(db_genre)
    return db_genres


def search_params_for_series(**lookup_params):
    search_params = {
        'tvmaze_id': lookup_params.get('tvmaze_id'),
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
    return session.query(TVMazeLookup).filter(TVMazeLookup.search_name == title.lower()).first()


@with_session
def add_to_lookup(session=None, title=None, series=None):
    log.debug('trying to add search title {0} to series {1} in lookup table'.format(title, series.name))
    exist = session.query(TVMazeLookup).filter(TVMazeLookup.search_name == title.lower()).first()
    if exist:
        log.debug('title {0} already exist for series {1}, no need to save lookup'.format(title, series.name))
        return
    session.add(TVMazeLookup(search_name=title, series=series))


def prepare_lookup_for_tvmaze(**lookup_params):
    """
    Return a dict of params which is valid with tvmaze API lookups

    :param lookup_params: Search parameters
    :return: Dict of tvmaze recognizable key words
    """
    prepared_params = {}
    title = None
    series_name = lookup_params.get('series_name') or lookup_params.get('show_name') or lookup_params.get('title')
    if series_name:
        title, _ = split_title_year(series_name)
    # Support for when title is just a number
    if not title:
        title = series_name

    # Ensure we send native types to tvmaze lib as it does not handle new types very well
    prepared_params['tvmaze_id'] = lookup_params.get('tvmaze_id')
    prepared_params['thetvdb_id'] = lookup_params.get('tvdb_id') or lookup_params.get('trakt_series_tvdb_id')
    prepared_params['tvrage_id'] = lookup_params.get('tvrage_id') or lookup_params.get('trakt_series_tvrage_id')
    prepared_params['imdb_id'] = lookup_params.get('imdb_id')
    prepared_params['show_name'] = native(title) if title else None

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

        prepared_params = prepare_lookup_for_tvmaze(**lookup_params)
        log.debug('trying to fetch series {0} from tvmaze'.format(title))
        tvmaze_show = get_show(**prepared_params)

        # See if series already exist in cache
        series = session.query(TVMazeSeries).filter(TVMazeSeries.tvmaze_id == tvmaze_show['id']).first()
        if series:
            log.debug('series {0} is already in cache, checking for expiration'.format(series.name))
            if series.expired:
                series.update(tvmaze_show, session)
        else:
            log.debug('creating new series {0} in tvmaze_series db'.format(tvmaze_show['name']))
            series = TVMazeSeries(tvmaze_show, session)
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
        if lookup_type == 'sequence':
            raise LookupError('TVMaze does not support sequence type searches')
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
            and_(TVMazeEpisodes.series_id == series.tvmaze_id,
                 TVMazeEpisodes.season_number == season_number,
                 TVMazeEpisodes.number == episode_number)
        ).one_or_none()

        # Logic for cache only mode
        if only_cached:
            if episode:
                log.debug('forcing cache for episode id {3}, number{0}, season {1} for show {2}'
                          .format(episode.number, episode.season_number, series.name, episode.tvmaze_id))
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
            episode_date = datetime.strftime(episode_date, '%Y-%m-%d')
            tvmaze_episode = get_episode(series.tvmaze_id, date=episode_date)[0]
        else:
            # TODO will this match all series_id types?
            log.debug(
                'fetching episode {0} season {1} for series_id {2} for tvmaze'.format(episode_number,
                                                                                      season_number,
                                                                                      series.tvmaze_id))
            tvmaze_episode = get_episode(series.tvmaze_id, season=season_number, number=episode_number)
        # See if episode exists in DB
        try:
            episode = session.query(TVMazeEpisodes).filter(
                or_(TVMazeEpisodes.tvmaze_id == tvmaze_episode['id'],
                    and_(
                        TVMazeEpisodes.number == tvmaze_episode['number'],
                        TVMazeEpisodes.season_number == tvmaze_episode['season'],
                        TVMazeEpisodes.series_id == series.tvmaze_id)
                    )
            ).one_or_none()
        except MultipleResultsFound:
            # TVMaze must have fucked up and now we have to clean up that mess. Delete any row for this season
            # that hasn't been updated in the last hour. Can't trust any of the cached data, but deleting new data
            # might have some unintended consequences.
            log.warning('Episode lookup in cache returned multiple results. Deleting the cached data.')
            deleted_rows = session.query(TVMazeEpisodes).filter(
                and_(
                    TVMazeEpisodes.season_number == tvmaze_episode['season'],
                    TVMazeEpisodes.series_id == series.tvmaze_id)
            ).filter(TVMazeEpisodes.last_update <= datetime.now() - timedelta(hours=1)).delete()
            log.debug('Deleted %s rows', deleted_rows)
            episode = None

        if episode:
            log.debug('found expired episode {0} in cache, refreshing data.'.format(episode.tvmaze_id))
            episode.update(tvmaze_episode)
        else:
            log.debug('creating new episode for show {0}'.format(series.name))
            episode = TVMazeEpisodes(tvmaze_episode, series.tvmaze_id)
            session.add(episode)

        return episode


def get_show(show_name=None, tvmaze_id=None, imdb_id=None, tvrage_id=None, thetvdb_id=None):
    if tvmaze_id:
        return tvmaze_lookup('tvmaze_id', [tvmaze_id])
    if imdb_id:
        return tvmaze_lookup('imdb_id', [imdb_id])
    if tvrage_id:
        return tvmaze_lookup('tvrage_id', [tvrage_id])
    if thetvdb_id:
        return tvmaze_lookup('thetvdb_id', [thetvdb_id])
    if show_name:
        return tvmaze_lookup('show_name', [show_name])
    raise LookupError('Not enough parameters sent for series lookup')


def get_episode(series_id, date=None, number=None, season=None):
    if date:
        return tvmaze_lookup('date', [series_id, date])
    elif number and season:
        return tvmaze_lookup('number', [series_id, season, number])
    raise LookupError('Not enough parameters sent for episode lookup')


def tvmaze_lookup(lookup_type, lookup_values):
    """
    Build the URL and return the reply from TVMaze API

    :param lookup_type: Selects the endpoint that will be used
    :param lookup_values: A list of values to be used in the URL
    :return: A JSON reply from the API
    """
    lookup_url = BASE_URL + TVMAZE_ENDPOINTS[lookup_type].format(*lookup_values)
    log.debug('querying tvmaze API with the following URL: %s', lookup_url)
    try:
        result = requests.get(lookup_url).json()
    except RequestException as e:
        raise LookupError(e)
    return result


@event('plugin.register')
def register_plugin():
    plugin.register(APITVMaze, 'api_tvmaze', api_ver=2)
