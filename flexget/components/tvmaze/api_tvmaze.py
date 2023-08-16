from datetime import datetime, timedelta

from dateutil import parser
from loguru import logger
from requests.exceptions import RequestException
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Unicode,
    and_,
    or_,
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import MultipleResultsFound

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils import requests
from flexget.utils.database import json_synonym, with_session
from flexget.utils.tools import split_title_year

logger = logger.bind(name='api_tvmaze')

DB_VERSION = 7
Base = db_schema.versioned_base('tvmaze', DB_VERSION)
UPDATE_INTERVAL = 7  # Used for expiration, number is in days
BASE_URL = 'https://api.tvmaze.com'

TVMAZE_SHOW_PATH = "/shows/{}"
TVMAZE_LOOKUP_PATH = "/lookup/shows"
TVMAZE_SEARCH_PATH = "/singlesearch/shows"
TVMAZE_EPISODES_BY_DATE_PATH = "/shows/{}/episodesbydate"
TVMAZE_EPISODES_BY_NUMBER_PATH = "/shows/{}/episodebynumber"
TVMAZE_SEASONS = '/shows/{}/seasons'


@db_schema.upgrade('tvmaze')
def upgrade(ver, session):
    if ver is None or ver < 7:
        raise db_schema.UpgradeImpossible
    return ver


class TVMazeGenre(Base):
    __tablename__ = 'tvmaze_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode, unique=True)


genres_table = Table(
    'tvmaze_series_genres',
    Base.metadata,
    Column('series_id', Integer, ForeignKey('tvmaze_series.tvmaze_id')),
    Column('genre_id', Integer, ForeignKey('tvmaze_genres.id')),
)

Base.register_table(genres_table)


class TVMazeLookup(Base):
    __tablename__ = 'tvmaze_lookup'

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_name = Column(Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.tvmaze_id'))
    series = relationship('TVMazeSeries', backref='search_strings')

    def __init__(self, search_name, series_id=None, series=None):
        self.search_name = search_name.lower()
        if series_id:
            self.series_id = series_id
        if series:
            self.series = series

    def __repr__(self):
        return f'<TVMazeLookup(search_name={self.search_name},series_id={self.series_id})'


class TVMazeSeries(Base):
    __tablename__ = 'tvmaze_series'

    tvmaze_id = Column(Integer, primary_key=True)
    status = Column(Unicode)
    rating = Column(Float)
    genres = relationship(TVMazeGenre, secondary=genres_table)
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
    episodes = relationship(
        'TVMazeEpisodes',
        order_by='TVMazeEpisodes.season_number',
        cascade='all, delete, delete-orphan',
        backref='series',
    )
    seasons = relationship(
        'TVMazeSeason',
        order_by='TVMazeSeason.number',
        cascade='all, delete, delete-orphan',
        backref='series',
    )

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
            'last_update': self.last_update,
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
        self.premiered = (
            parser.parse(series.get('premiered'), ignoretz=True)
            if series.get('premiered')
            else None
        )
        self.year = int(series.get('premiered')[:4]) if series.get('premiered') else None
        self.summary = series['summary']
        self.webchannel = series.get('web_channel')['name'] if series.get('web_channel') else None
        self.runtime = series['runtime']
        self.show_type = series['type']
        self.network = series.get('network')['name'] if series.get('network') else None
        self.last_update = datetime.now()

        self.genres = get_db_genres(series['genres'], session)
        self.seasons = self.populate_seasons(series)

    def __repr__(self):
        return '<TVMazeSeries(title={},id={},last_update={})>'.format(
            self.name,
            self.tvmaze_id,
            self.last_update,
        )

    def __str__(self):
        return self.name

    @property
    def expired(self):
        if not self.last_update:
            logger.debug('no last update attribute, series set for update')
            return True
        time_dif = datetime.now() - self.last_update
        expiration = time_dif.days > UPDATE_INTERVAL
        return expiration

    def populate_seasons(self, series=None):
        if series and '_embedded' in series and series['_embedded'].get('seasons'):
            seasons = series['_embedded']['seasons']
        else:
            seasons = get_seasons(self.tvmaze_id)
        return [TVMazeSeason(season, self.tvmaze_id) for season in seasons]


class TVMazeSeason(Base):
    __tablename__ = 'tvmaze_seasons'

    tvmaze_id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('tvmaze_series.tvmaze_id'), nullable=False)

    number = Column(Integer)
    url = Column(String)
    name = Column(Unicode)
    episode_order = Column(Integer)
    airdate = Column(DateTime)
    end_date = Column(DateTime)
    network = Column(Unicode)
    web_channel = Column(Unicode)
    image = Column(String)
    summary = Column(Unicode)

    def __init__(self, season, series_id):
        self.tvmaze_id = season['id']
        self.series_id = series_id
        self.number = season['number']
        self.update(season)

    def update(self, season):
        self.url = season['url']
        self.name = season['name']
        self.end_date = (
            parser.parse(season.get('endDate'), ignoretz=True) if season.get('endDate') else None
        )
        self.airdate = (
            parser.parse(season['premiereDate'], ignoretz=True)
            if season.get('premiereDate')
            else None
        )
        self.web_channel = season['web_channel']['name'] if season.get('web_channel') else None
        self.network = season['network']['name'] if season.get('network') else None
        self.image = season['image']['original'] if season.get('image') else None
        self.summary = season['summary']


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
            'last_update': self.last_update,
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
        self.airdate = (
            datetime.strptime(episode.get('airdate'), '%Y-%m-%d')
            if episode.get('airdate')
            else None
        )
        self.url = episode['url']
        self.original_image = (
            episode.get('image').get('original') if episode.get('image') else None
        )
        self.medium_image = episode.get('image').get('medium') if episode.get('image') else None
        self.airstamp = (
            parser.parse(episode.get('airstamp'), ignoretz=True)
            if episode.get('airstamp')
            else None
        )
        self.runtime = episode['runtime']
        self.last_update = datetime.now()

    @property
    def expired(self):
        if not self.last_update:
            logger.debug('no last update attribute, episode set for update')
            return True
        time_dif = datetime.now() - self.last_update
        expiration = time_dif.days > UPDATE_INTERVAL
        if expiration:
            logger.debug(
                'episode {}, season {} for series {} is expired.',
                self.number,
                self.season_number,
                self.series_id,
            )
        return expiration


def get_db_genres(genres, session):
    db_genres = []
    for genre in genres:
        db_genre = session.query(TVMazeGenre).filter(TVMazeGenre.name == genre).first()
        if not db_genre:
            db_genre = TVMazeGenre(name=genre)
            logger.trace('adding genre {} to db', genre)
            session.add(db_genre)
        else:
            logger.trace('genre {} found in db, returning', db_genre.name)
        db_genres.append(db_genre)
    return db_genres


def search_params_for_series(**lookup_params):
    search_params = {
        'tvmaze_id': lookup_params.get('tvmaze_id'),
        'tvdb_id': lookup_params.get('tvdb_id'),
        'tvrage_id': lookup_params.get('tvrage_id'),
        'name': lookup_params.get('title') or lookup_params.get('series_name'),
    }
    logger.debug('returning search params for series lookup: {}', search_params)
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
        logger.debug(
            'searching db {} for the values {}',
            cache_type.__tablename__,
            list(search_params.items()),
        )
        result = (
            session.query(cache_type)
            .filter(
                or_(getattr(cache_type, col) == val for col, val in search_params.items() if val)
            )
            .first()
        )
    return result


@with_session
def from_lookup(session=None, title=None):
    logger.debug('searching lookup table using title {}', title)
    return session.query(TVMazeLookup).filter(TVMazeLookup.search_name == title.lower()).first()


@with_session
def add_to_lookup(session=None, title=None, series=None):
    logger.debug('trying to add search title {} to series {} in lookup table', title, series.name)
    exist = session.query(TVMazeLookup).filter(TVMazeLookup.search_name == title.lower()).first()
    if exist:
        logger.debug(
            'title {} already exist for series {}, no need to save lookup', title, series.name
        )
        return
    result = TVMazeLookup(search_name=title)
    session.add(result)
    result.series = series


def prepare_lookup_for_tvmaze(**lookup_params):
    """
    Return a dict of params which is valid with tvmaze API lookups

    :param lookup_params: Search parameters
    :return: Dict of tvmaze recognizable key words
    """
    prepared_params = {}
    title = None
    series_name = (
        lookup_params.get('series_name')
        or lookup_params.get('show_name')
        or lookup_params.get('title')
    )
    if series_name:
        title, _ = split_title_year(series_name)
    # Support for when title is just a number
    if not title:
        title = series_name

    # Ensure we send native types to tvmaze lib as it does not handle new types very well
    prepared_params['tvmaze_id'] = lookup_params.get('tvmaze_id')
    prepared_params['thetvdb_id'] = lookup_params.get('tvdb_id') or lookup_params.get(
        'trakt_series_tvdb_id'
    )
    prepared_params['tvrage_id'] = lookup_params.get('tvrage_id') or lookup_params.get(
        'trakt_series_tvrage_id'
    )
    prepared_params['imdb_id'] = lookup_params.get('imdb_id')
    prepared_params['show_name'] = title or None

    return prepared_params


class APITVMaze:
    @staticmethod
    @with_session
    def series_lookup(session=None, only_cached=False, **lookup_params):
        search_params = search_params_for_series(**lookup_params)
        # Searching cache first
        series = from_cache(session=session, cache_type=TVMazeSeries, search_params=search_params)

        search = None
        # Preparing search from lookup table
        title = (
            lookup_params.get('series_name')
            or lookup_params.get('show_name')
            or lookup_params.get('title')
        )
        if not series and title:
            logger.debug(
                'did not find exact match for series {} in cache, looking in search table',
                search_params['name'],
            )
            search = from_lookup(session=session, title=title)
            if search and search.series:
                series = search.series
                logger.debug('found series {} from search table', series.name)

        if only_cached:
            if series:  # If force_cache is True, return series even if it expired
                logger.debug('forcing cache for series {}', series.name)
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            logger.debug('returning series {} from cache', series.name)
            return series

        prepared_params = prepare_lookup_for_tvmaze(**lookup_params)
        logger.debug('trying to fetch series {} from tvmaze', title)
        tvmaze_show = get_show(**prepared_params)

        # See if series already exist in cache
        series = (
            session.query(TVMazeSeries).filter(TVMazeSeries.tvmaze_id == tvmaze_show['id']).first()
        )
        if series:
            logger.debug('series {} is already in cache, checking for expiration', series.name)
            if series.expired:
                series.update(tvmaze_show, session)
        else:
            logger.debug('creating new series {} in tvmaze_series db', tvmaze_show['name'])
            series = TVMazeSeries(tvmaze_show, session)
            session.add(series)

        # Check if show returned from lookup table as expired. Relevant only if search by title
        if title:
            if series and title.lower() == series.name.lower():
                return series
            elif series and not search:
                logger.debug(
                    'mismatch between search title {} and series title {}. '
                    'saving in lookup table',
                    title,
                    series.name,
                )
                add_to_lookup(session=session, title=title, series=series)
            elif series and search:
                logger.debug('Updating search result in db')
                search.series = series
        return series

    @staticmethod
    @with_session
    def season_lookup(session=None, only_cached=False, **lookup_params):
        series_name = lookup_params.get('series_name') or lookup_params.get('title')
        show_id = lookup_params.get('tvmaze_id') or lookup_params.get('tvdb_id')

        season_number = lookup_params.get('series_season')

        # Verify we have enough parameters for search
        if not any([series_name, show_id, season_number]):
            raise LookupError('Not enough parameters to lookup episode')

        # Get series
        series = APITVMaze.series_lookup(session=session, only_cached=only_cached, **lookup_params)
        if not series:
            raise LookupError(
                f'Could not find series with the following parameters: {lookup_params}'
            )
        session.flush()
        # See if season already exists in cache
        logger.debug('searching for season {} of show {} in cache', season_number, series.name)
        season = (
            session.query(TVMazeSeason)
            .filter(TVMazeSeason.series_id == series.tvmaze_id)
            .filter(TVMazeSeason.number == season_number)
            .one_or_none()
        )

        # Logic for cache only mode
        if only_cached:
            if season:
                logger.debug('forcing cache for season {} of show {}', season_number, series.name)
                return season

        if season and not series.expired:
            logger.debug('returning season {} of show {}', season_number, series.name)
            return season

        # If no season has been found try refreshing the series seasons
        series.populate_seasons()

        # Query again
        season = (
            session.query(TVMazeSeason)
            .filter(TVMazeSeason.tvmaze_id == series.tvmaze_id)
            .filter(TVMazeSeason.number == season_number)
            .one_or_none()
        )
        if season:
            return season

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
            raise LookupError(
                f'Could not find series with the following parameters: {lookup_params}'
            )

        # See if episode already exists in cache
        logger.debug('searching for episode of show {} in cache', series.name)
        episode = (
            session.query(TVMazeEpisodes)
            .filter(
                and_(
                    TVMazeEpisodes.series_id == series.tvmaze_id,
                    TVMazeEpisodes.season_number == season_number,
                    TVMazeEpisodes.number == episode_number,
                )
            )
            .one_or_none()
        )

        # Logic for cache only mode
        if only_cached:
            if episode:
                logger.debug(
                    'forcing cache for episode id {3}, number{0}, season {1} for show {2}',
                    episode.number,
                    episode.season_number,
                    series.name,
                    episode.tvmaze_id,
                )
                return episode
        if episode and not episode.expired:
            logger.debug(
                'found episode id {3}, number {0}, season {1} for show {2} in cache',
                episode.number,
                episode.season_number,
                series.name,
                episode.tvmaze_id,
            )

            return episode

        # Lookup episode via its type (number or airdate)
        if lookup_type == 'date':
            episode_date = datetime.strftime(episode_date, '%Y-%m-%d')
            tvmaze_episode = get_episode(series.tvmaze_id, date=episode_date)[0]
        else:
            # TODO will this match all series_id types?
            logger.debug(
                'fetching episode {0} season {1} for series_id {2} for tvmaze',
                episode_number,
                season_number,
                series.tvmaze_id,
            )
            tvmaze_episode = get_episode(
                series.tvmaze_id, season=season_number, number=episode_number
            )
        # See if episode exists in DB
        try:
            episode = (
                session.query(TVMazeEpisodes)
                .filter(
                    or_(
                        TVMazeEpisodes.tvmaze_id == tvmaze_episode['id'],
                        and_(
                            TVMazeEpisodes.number == tvmaze_episode['number'],
                            TVMazeEpisodes.season_number == tvmaze_episode['season'],
                            TVMazeEpisodes.series_id == series.tvmaze_id,
                        ),
                    )
                )
                .one_or_none()
            )
        except MultipleResultsFound:
            # TVMaze must have fucked up and now we have to clean up that mess. Delete any row for this season
            # that hasn't been updated in the last hour. Can't trust any of the cached data, but deleting new data
            # might have some unintended consequences.
            logger.warning(
                'Episode lookup in cache returned multiple results. Deleting the cached data.'
            )
            deleted_rows = (
                session.query(TVMazeEpisodes)
                .filter(
                    and_(
                        TVMazeEpisodes.season_number == tvmaze_episode['season'],
                        TVMazeEpisodes.series_id == series.tvmaze_id,
                    )
                )
                .filter(TVMazeEpisodes.last_update <= datetime.now() - timedelta(hours=1))
                .delete()
            )
            logger.debug('Deleted {} rows', deleted_rows)
            episode = None

        if episode:
            logger.debug('found expired episode {} in cache, refreshing data.', episode.tvmaze_id)
            episode.update(tvmaze_episode)
        else:
            logger.debug('creating new episode for show {}', series.name)
            episode = TVMazeEpisodes(tvmaze_episode, series.tvmaze_id)
            session.add(episode)

        return episode


def get_show(show_name=None, tvmaze_id=None, imdb_id=None, tvrage_id=None, thetvdb_id=None):
    if not any(param for param in [show_name, tvmaze_id, imdb_id, tvrage_id, thetvdb_id]):
        raise LookupError('Not enough parameters sent for series lookup')
    params = {'embed': 'seasons'}
    if tvmaze_id:
        url = TVMAZE_SHOW_PATH.format(tvmaze_id)
    elif imdb_id:
        url = TVMAZE_LOOKUP_PATH
        params['imdb'] = imdb_id
    elif tvrage_id:
        url = TVMAZE_LOOKUP_PATH
        params['tvrage'] = tvrage_id
    elif thetvdb_id:
        url = TVMAZE_LOOKUP_PATH
        params['thetvdb'] = thetvdb_id
    else:
        params['q'] = show_name
        url = TVMAZE_SEARCH_PATH
    return tvmaze_lookup(url, params=params)


def get_episode(series_id, date=None, number=None, season=None):
    if date:
        return tvmaze_lookup(TVMAZE_EPISODES_BY_DATE_PATH.format(series_id), params={'date': date})
    elif number and season:
        return tvmaze_lookup(
            TVMAZE_EPISODES_BY_NUMBER_PATH.format(series_id),
            params={'season': season, 'number': number},
        )
    raise LookupError('Not enough parameters sent for episode lookup')


def get_seasons(series_id):
    return tvmaze_lookup(TVMAZE_SEASONS.format(series_id))


def tvmaze_lookup(lookup_url, **kwargs):
    """
    Build the URL and return the reply from TVMaze API

    :param lookup_type: Selects the endpoint that will be used
    :param lookup_values: A list of values to be used in the URL
    :return: A JSON reply from the API
    """
    url = BASE_URL + lookup_url
    logger.debug('querying tvmaze API with the following URL: {}', url)
    try:
        result = requests.get(url, **kwargs).json()
    except RequestException as e:
        raise LookupError(e.args[0])
    return result


@event('plugin.register')
def register_plugin():
    plugin.register(APITVMaze, 'api_tvmaze', api_ver=2, interfaces=[])
