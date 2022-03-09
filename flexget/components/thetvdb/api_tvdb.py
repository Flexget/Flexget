from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Table, Text, Unicode
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema
from flexget.utils import requests
from flexget.utils.database import Session, json_synonym, text_date_synonym, with_session
from flexget.utils.simple_persistence import SimplePersistence
from flexget.utils.tools import chunked, split_title_year

logger = logger.bind(name='api_tvdb')
Base = db_schema.versioned_base('api_tvdb', 7)

persist = SimplePersistence('api_tvdb')

SEARCH_RESULT_EXPIRATION_DAYS = 3


class TVDBRequest:
    # This is a FlexGet API key
    API_KEY = '4D297D8CFDE0E105'
    BASE_URL = 'https://api.thetvdb.com/'
    BANNER_URL = 'http://thetvdb.com/banners/'

    def __init__(self, username=None, account_id=None, api_key=None):
        self.username = username
        self.account_id = account_id
        self.api_key = api_key
        self.auth_key = self.username.lower() if self.username else 'default'

    def get_auth_token(self, refresh=False):
        with Session() as session:
            auth_token = session.query(TVDBTokens).filter(TVDBTokens.name == self.auth_key).first()
            if not auth_token:
                auth_token = TVDBTokens()
                auth_token.name = self.auth_key

            if refresh or auth_token.has_expired():
                data = {'apikey': TVDBRequest.API_KEY}
                if self.username:
                    data['username'] = self.username
                if self.account_id:
                    data['userkey'] = self.account_id
                if self.api_key:
                    data['apikey'] = self.api_key

                logger.debug(
                    'Authenticating to TheTVDB with {}',
                    self.username if self.username else 'api_key',
                )

                auth_token.token = (
                    requests.post(TVDBRequest.BASE_URL + 'login', json=data).json().get('token')
                )
                auth_token.refreshed = datetime.now()
                auth_token = session.merge(auth_token)

            return auth_token.token

    def _request(self, method, endpoint, **params):
        url = TVDBRequest.BASE_URL + endpoint
        language = params.pop('language', 'en')
        headers = {'Authorization': f'Bearer {self.get_auth_token()}', 'Accept-Language': language}
        data = params.pop('data', None)

        result = requests.request(
            method, url, params=params, headers=headers, raise_status=False, json=data
        )
        if result.status_code == 401:
            logger.debug('Auth token expired, refreshing')
            headers['Authorization'] = f'Bearer {self.get_auth_token(refresh=True)}'
            result = requests.request(
                method, url, params=params, headers=headers, raise_status=False, json=data
            )
        result.raise_for_status()
        result = result.json()

        if result.get('errors'):
            logger.debug('Result contains errors: {}', result['errors'])
            # a hack to make sure it doesn't raise exception on a simple invalidLanguage. This is because tvdb
            # has a tendency to contain bad data and randomly return this error for no reason
            if len(result['errors']) > 1 or 'invalidLanguage' not in result['errors']:
                raise LookupError(f'Error processing request on tvdb: {result["errors"]}')

        return result

    def get(self, endpoint, **params):
        result = self._request('get', endpoint, **params)
        return result.get('data')

    def post(self, endpoint, **params):
        result = self._request('post', endpoint, **params)
        return result.get('data')

    def put(self, endpoint, **params):
        result = self._request('put', endpoint, **params)
        return result.get('data')

    def delete(self, endpoint, **params):
        return self._request('delete', endpoint, **params)


@db_schema.upgrade('api_tvdb')
def upgrade(ver, session):
    if ver is None or ver <= 6:
        raise db_schema.UpgradeImpossible
    return ver


# association tables
genres_table = Table(
    'tvdb_series_genres',
    Base.metadata,
    Column('series_id', Integer, ForeignKey('tvdb_series.id')),
    Column('genre_id', Integer, ForeignKey('tvdb_genres.id')),
)
Base.register_table(genres_table)


class TVDBTokens(Base):
    __tablename__ = 'tvdb_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode)
    token = Column(Text)
    refreshed = Column(DateTime)

    def has_expired(self):
        if not self.token or not self.refreshed:
            return True

        seconds = (datetime.now() - self.refreshed).total_seconds()
        if seconds >= 86400:
            return True

        return False


class TVDBSeries(Base):
    __tablename__ = "tvdb_series"

    id = Column(Integer, primary_key=True, autoincrement=False)
    last_updated = Column(Integer)
    expired = Column(Boolean)
    name = Column(Unicode)
    language = Column(Unicode)
    rating = Column(Float)
    status = Column(Unicode)
    runtime = Column(Integer)
    airs_time = Column(Unicode)
    airs_dayofweek = Column(Unicode)
    content_rating = Column(Unicode)
    network = Column(Unicode)
    overview = Column(Unicode)
    imdb_id = Column(Unicode)
    zap2it_id = Column(Unicode)
    _banner = Column('banner', Unicode)

    _first_aired = Column('first_aired', DateTime)
    first_aired = text_date_synonym('_first_aired')
    _aliases = Column('aliases', Unicode)
    aliases = json_synonym('_aliases')
    _actors = Column('actors', Unicode)
    actors_list = json_synonym('_actors')
    _posters = Column('posters', Unicode)
    posters_list = json_synonym('_posters')

    _genres = relation('TVDBGenre', secondary=genres_table)
    genres = association_proxy('_genres', 'name')

    episodes = relation('TVDBEpisode', backref='series', cascade='all, delete, delete-orphan')

    def __init__(self, tvdb_id, language):
        """
        Looks up movie on tvdb and creates a new database model for it.
        These instances should only be added to a session via `session.merge`.
        """
        self.id = tvdb_id

        try:
            series = TVDBRequest().get(f'series/{self.id}', language=language)
        except requests.RequestException as e:
            raise LookupError(f'Error updating data from tvdb: {e}')

        self.language = language or 'en'
        self.last_updated = series['lastUpdated']
        self.name = series['seriesName']
        self.rating = float(series['siteRating']) if series['siteRating'] else 0.0
        self.status = series['status']
        self.runtime = int(series['runtime']) if series['runtime'] else 0
        self.airs_time = series['airsTime']
        self.airs_dayofweek = series['airsDayOfWeek']
        self.content_rating = series['rating']
        self.network = series['network']
        self.overview = series['overview']
        self.imdb_id = series['imdbId']
        self.zap2it_id = series['zap2itId']
        self.first_aired = series['firstAired']
        self.expired = False
        self.aliases = series['aliases']
        self._banner = series['banner']
        self._genres = [TVDBGenre(id=name) for name in series['genre']] if series['genre'] else []

        if not self.name:
            raise LookupError(
                f'Not possible to get name to series with id {self.id} in language \'{self.language}\''
            )

        if self.first_aired is None:
            logger.debug(
                'Falling back to getting first episode aired date for series {}', self.name
            )
            try:
                episode = TVDBRequest().get(
                    f'series/{self.id}/episodes/query?airedSeason=1&airedEpisode=1',
                    language=language,
                )
                self.first_aired = episode[0]['firstAired']
            except requests.RequestException:
                logger.error('Failed to get first episode for series {}', self.name)

        # Actors and Posters are lazy populated
        self._actors = None
        self._posters = None

    def __repr__(self):
        return f'<TVDBSeries name={self.name},tvdb_id={self.id}>'

    @property
    def banner(self):
        if self._banner:
            return TVDBRequest.BANNER_URL + self._banner

    @property
    def actors(self):
        return self.get_actors()

    @property
    def posters(self):
        return self.get_posters()

    def get_actors(self):
        if not self._actors:
            logger.debug('Looking up actors for series {}', self.name)
            try:
                actors_query = TVDBRequest().get(f'series/{self.id}/actors')
                self.actors_list = [a['name'] for a in actors_query] if actors_query else []
            except requests.RequestException as e:
                if None is not e.response and e.response.status_code == 404:
                    self.actors_list = []
                else:
                    raise LookupError(f'Error updating actors from tvdb: {e}')

        return self.actors_list

    def get_posters(self):
        if not self._posters:
            logger.debug('Getting top 5 posters for series {}', self.name)
            try:
                poster_main = TVDBRequest().get(f'series/{self.id}').get('poster')
                poster_query = TVDBRequest().get(
                    f'series/{self.id}/images/query', keyType='poster'
                )
                self.posters_list = [poster_main] if poster_main else []
                self.posters_list += (
                    [p['fileName'] for p in poster_query[:5]] if poster_query else []
                )
            except requests.RequestException as e:
                if None is not e.response and e.response.status_code == 404:
                    self.posters_list = []
                else:
                    raise LookupError(f'Error updating posters from tvdb: {e}')

        return [TVDBRequest.BANNER_URL + p for p in self.posters_list[:5]]

    def to_dict(self):
        return {
            'aliases': [a for a in self.aliases],
            'tvdb_id': self.id,
            'last_updated': datetime.fromtimestamp(self.last_updated).strftime(
                '%Y-%m-%d %H:%M:%S'
            ),
            'expired': self.expired,
            'series_name': self.name,
            'language': self.language,
            'rating': self.rating,
            'status': self.status,
            'runtime': self.runtime,
            'airs_time': self.airs_time,
            'airs_dayofweek': self.airs_dayofweek,
            'content_rating': self.content_rating,
            'network': self.network,
            'overview': self.overview,
            'imdb_id': self.imdb_id,
            'zap2it_id': self.zap2it_id,
            'banner': self.banner,
            'posters': self.posters,
            'genres': [g for g in self.genres],
            'first_aired': self.first_aired,
        }


class TVDBGenre(Base):
    __tablename__ = 'tvdb_genres'
    id = Column(Unicode, primary_key=True)

    @property
    def name(self):
        return self.id


class TVDBEpisode(Base):
    __tablename__ = 'tvdb_episodes'

    id = Column(Integer, primary_key=True, autoincrement=False)
    expired = Column(Boolean)
    last_updated = Column(Integer)
    season_number = Column(Integer)
    episode_number = Column(Integer)
    absolute_number = Column(Integer)
    name = Column(Unicode)
    overview = Column(Unicode)
    rating = Column(Float)
    director = Column(Unicode)
    _image = Column(Unicode)
    _first_aired = Column('firstaired', DateTime)
    first_aired = text_date_synonym('_first_aired')

    series_id = Column(Integer, ForeignKey('tvdb_series.id'), nullable=False)

    def __init__(self, series_id, ep_id, language=None):
        """
        Looks up movie on tvdb and creates a new database model for it.
        These instances should only be added to a session via `session.merge`.
        """
        self.series_id = series_id
        self.id = ep_id
        self.expired = False
        try:
            episode = TVDBRequest().get(f'episodes/{self.id}', language=language)
        except requests.RequestException as e:
            raise LookupError(f'Error updating data from tvdb: {e}')

        self.id = episode['id']
        self.last_updated = episode['lastUpdated']
        self.season_number = episode['airedSeason']
        self.episode_number = episode['airedEpisodeNumber']
        self.absolute_number = episode['absoluteNumber']
        self.name = episode['episodeName']
        self.overview = episode['overview']
        self.director = ', '.join(episode['directors'])
        self._image = episode['filename']
        self.rating = episode['siteRating']
        self.first_aired = episode['firstAired']

    def __repr__(self):
        return (
            f'<TVDBEpisode series={self.series.name},season={self.season_number},'
            f'episode={self.episode_number}>'
        )

    def to_dict(self):
        return {
            'id': self.id,
            'expired': self.expired,
            'last_update': self.last_updated,
            'season_number': self.season_number,
            'episode_number': self.episode_number,
            'absolute_number': self.absolute_number,
            'episode_name': self.name,
            'overview': self.overview,
            'director': self.director,
            'rating': self.rating,
            'image': self.image,
            'first_aired': self.first_aired,
            'series_id': self.series_id,
        }

    @property
    def image(self):
        if self._image:
            return TVDBRequest.BANNER_URL + self._image


class TVDBSearchResult(Base):
    __tablename__ = 'tvdb_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, nullable=False, unique=True)
    series_id = Column(Integer, ForeignKey('tvdb_series.id'), nullable=True)
    series = relation(TVDBSeries, backref='search_strings')

    def __init__(self, search, series_id=None, series=None):
        self.search = search.lower()
        if series_id:
            self.series_id = series_id
        if series:
            self.series = series


class TVDBSeriesSearchResult(Base):
    """
    This table will hold a single result that results from the /search/series endpoint,
    which return a series with a minimal set of parameters.
    """

    __tablename__ = 'tvdb_series_search_results'

    id = Column(Integer, primary_key=True, autoincrement=False)
    lookup_term = Column(Unicode)

    name = Column(Unicode)
    status = Column(Unicode)
    network = Column(Unicode)
    overview = Column(Unicode)

    _banner = Column('banner', Unicode)

    _first_aired = Column('first_aired', DateTime)
    first_aired = text_date_synonym('_first_aired')

    _aliases = Column('aliases', Unicode)
    aliases = json_synonym('_aliases')

    created_at = Column(DateTime)
    search_name = Column(Unicode)

    def __init__(self, series, lookup_term=None):
        self.lookup_term = lookup_term
        self.id = series['id']
        self.name = series['seriesName']
        self.first_aired = series['firstAired']
        self.network = series['network']
        self.overview = series['overview']
        self.status = series['status']
        self._banner = series['banner']
        self.aliases = series['aliases']
        self.created_at = datetime.now()

    @property
    def banner(self):
        if self._banner:
            return TVDBRequest.BANNER_URL + self._banner

    def to_dict(self):
        return {
            'aliases': [a for a in self.aliases],
            'banner': self.banner,
            'first_aired': self.first_aired,
            'tvdb_id': self.id,
            'network': self.network,
            'overview': self.overview,
            'series_name': self.name,
            'status': self.status,
        }

    @property
    def expired(self):
        logger.debug('checking series {} for expiration', self.name)
        if datetime.now() - self.created_at >= timedelta(days=SEARCH_RESULT_EXPIRATION_DAYS):
            logger.debug('series {} is expires, should re-fetch', self.name)
            return True
        logger.debug('series {} is not expired', self.name)
        return False


def find_series_id(name, language=None):
    """Looks up the tvdb id for a series"""
    try:
        series = TVDBRequest().get('search/series', name=name, language=language)
    except requests.RequestException as e:
        raise LookupError(f'Unable to get search results for {name}: {e}')

    name = name.lower()

    if not series:
        raise LookupError(f'No results found for {name}')

    # Cleanup results for sorting
    for s in series:
        if s['firstAired']:
            try:
                s['firstAired'] = datetime.strptime(s['firstAired'], "%Y-%m-%d")
            except ValueError:
                logger.warning(
                    'Invalid firstAired date "{}" when parsing series {} ',
                    s['firstAired'],
                    s['seriesName'],
                )
                s['firstAired'] = datetime(1970, 1, 1)
        else:
            s['firstAired'] = datetime(1970, 1, 1)

        s['names'] = [a.lower() for a in s.get('aliases')] if s.get('aliases') else []
        if s.get('seriesName'):
            s['names'].append(s.get('seriesName').lower())
        s['running'] = True if s['status'] == 'Continuing' else False

        for n in s['names']:
            # Exact matching by stripping our the year
            title = split_title_year(n)[0]
            if title not in s['names']:
                s['names'].append(title)

    # Sort by status, aired_date
    series = sorted(series, key=lambda x: (x['running'], x['firstAired']), reverse=True)

    for s in series:
        # Exact match
        if name in s['names']:
            return s['id']

    # If there is no exact match, pick the first result
    return series[0]['id']


def _update_search_strings(series, session, search=None):
    search_strings = series.search_strings
    aliases = [a.lower() for a in series.aliases] if series.aliases else []
    searches = [search.lower()] if search else []
    add = [series.name.lower()] + aliases + searches
    for name in set(add):
        if name not in search_strings:
            search_result = (
                session.query(TVDBSearchResult).filter(TVDBSearchResult.search == name).first()
            )
            if not search_result:
                search_result = TVDBSearchResult(search=name)
            search_result.series_id = series.id
            session.add(search_result)


@with_session
def lookup_series(name=None, tvdb_id=None, only_cached=False, session=None, language=None):
    """
    Look up information on a series. Will be returned from cache if available, and looked up online and cached if not.

    Either `name` or `tvdb_id` parameter are needed to specify the series.
    :param unicode name: Name of series.
    :param int tvdb_id: TVDb ID of series.
    :param bool only_cached: If True, will not cause an online lookup. LookupError will be raised if not available
        in the cache.
    :param session: An sqlalchemy session to be used to lookup and store to cache. Commit(s) may occur when passing in
        a session. If one is not supplied it will be created.
    :param language: Language abbreviation string to be sent to API

    :return: Instance of :class:`TVDBSeries` populated with series information. If session was not supplied, this will
        be a detached from the database, so relationships cannot be loaded.
    :raises: :class:`LookupError` if series cannot be looked up.
    """
    if not (name or tvdb_id):
        raise LookupError('No criteria specified for tvdb lookup')

    logger.debug("Looking up tvdb information for '{}'. TVDB ID: {}", name, tvdb_id)

    series = None

    def id_str():
        return f'<name={name},tvdb_id={tvdb_id}>'

    if tvdb_id:
        series = session.query(TVDBSeries).filter(TVDBSeries.id == tvdb_id).first()
    if not series and name:
        found = (
            session.query(TVDBSearchResult).filter(TVDBSearchResult.search == name.lower()).first()
        )
        if found and found.series:
            series = found.series
    if series:
        # Series found in cache, update if cache has expired.
        if not only_cached:
            mark_expired(session)
        if not only_cached and series.expired:
            logger.verbose('Data for {} has expired, refreshing from tvdb', series.name)
            try:
                updated_series = TVDBSeries(series.id, language)
                series = session.merge(updated_series)
                if series and series.name:
                    _update_search_strings(series, session, search=name)
            except LookupError as e:
                logger.warning(
                    'Error while updating from tvdb ({}), using cached data.', e.args[0]
                )
        else:
            logger.debug('Series {} information restored from cache.', id_str())
    else:
        if only_cached:
            raise LookupError(f'Series {id_str()} not found from cache')
        # There was no series found in the cache, do a lookup from tvdb
        logger.debug('Series {} not found in cache, looking up from tvdb.', id_str())
        if tvdb_id:
            series = session.merge(TVDBSeries(tvdb_id, language))
        elif name:
            tvdb_id = find_series_id(name, language=language)
            if tvdb_id:
                series = session.query(TVDBSeries).filter(TVDBSeries.id == tvdb_id).first()
                if not series:
                    series = session.merge(TVDBSeries(tvdb_id, language))
        if series and series.name:
            _update_search_strings(series, session, search=name)

    if not series:
        raise LookupError(f'No results found from tvdb for {id_str()}')
    if not series.name:
        raise LookupError('Tvdb result for series does not have a title.')

    return series


@with_session
def lookup_episode(
    name=None,
    season_number=None,
    episode_number=None,
    absolute_number=None,
    tvdb_id=None,
    first_aired=None,
    only_cached=False,
    session=None,
    language=None,
):
    """
    Look up information on an episode. Will be returned from cache if available, and looked up online and cached if not.

    Either `name` or `tvdb_id` parameter are needed to specify the series.
    Either `season_number` and `episode_number`, `absolute_number`, or `first_aired` are required to specify episode
     number.
    :param unicode name: Name of series episode belongs to.
    :param int tvdb_id: TVDb ID of series episode belongs to.
    :param int season_number: Season number of episode.
    :param int episode_number: Episode number of episode.
    :param int absolute_number: Absolute number of episode.
    :param date first_aired: Air date of episode. DateTime object.
    :param bool only_cached: If True, will not cause an online lookup. LookupError will be raised if not available
        in the cache.
    :param session: An sqlalchemy session to be used to lookup and store to cache. Commit(s) may occur when passing in
        a session. If one is not supplied it will be created, however if you need to access relationships you should
        pass one in.
    :param language: Language abbreviation string to be sent to API

    :return: Instance of :class:`TVDBEpisode` populated with series information.
    :raises: :class:`LookupError` if episode cannot be looked up.
    """
    # First make sure we have the series data
    series = lookup_series(name=name, tvdb_id=tvdb_id, only_cached=only_cached, session=session)

    if not series:
        raise LookupError(f'Series {name} ({tvdb_id}) not found from')

    ep_description = series.name
    query_params = {}
    episode = session.query(TVDBEpisode).filter(TVDBEpisode.series_id == series.id)

    if absolute_number is not None:
        episode = episode.filter(TVDBEpisode.absolute_number == absolute_number)
        query_params['absoluteNumber'] = absolute_number
        ep_description = f'{ep_description} absNo: {absolute_number}'

    if season_number is not None:
        episode = episode.filter(TVDBEpisode.season_number == season_number)
        query_params['airedSeason'] = season_number
        ep_description = f'{ep_description} s{season_number}'

    if episode_number is not None:
        episode = episode.filter(TVDBEpisode.episode_number == episode_number)
        query_params['airedEpisode'] = episode_number
        ep_description = f'{ep_description} e{episode_number}'

    if first_aired is not None:
        episode = episode.filter(TVDBEpisode.first_aired == first_aired)
        query_params['firstAired'] = datetime.strftime(first_aired, '%Y-%m-%d')
        ep_description = f'{ep_description} e{first_aired}'

    episode = episode.first()

    if episode:
        if episode.expired and not only_cached:
            logger.info('Data for {!r} has expired, refreshing from tvdb', episode)
            try:
                updated_episode = TVDBEpisode(series.id, episode.id)
                episode = session.merge(updated_episode)
            except LookupError as e:
                logger.warning('Error while updating from tvdb ({}), using cached data.', str(e))
        else:
            logger.debug('Using episode info for {} from cache.', ep_description)
    else:
        if only_cached:
            raise LookupError(f'Episode {ep_description} not found from cache')
        # There was no episode found in the cache, do a lookup from tvdb
        logger.debug('Episode {} not found in cache, looking up from tvdb.', ep_description)
        try:
            results = TVDBRequest().get(
                f'series/{series.id}/episodes/query', language=language, **query_params
            )
            if results:
                # Check if this episode id is already in our db
                episode = (
                    session.query(TVDBEpisode).filter(TVDBEpisode.id == results[0]['id']).first()
                )
                if not episode or (episode and episode.expired is not False):
                    updated_episode = TVDBEpisode(series.id, results[0]['id'], language=language)
                    episode = session.merge(updated_episode)

        except requests.RequestException as e:
            raise LookupError(f'Error looking up episode from TVDb ({e})')
    if episode:
        return episode
    else:
        raise LookupError(f'No results found for {ep_description}')


@with_session
def search_for_series(
    search_name=None, imdb_id=None, zap2it_id=None, force_search=None, session=None, language=None
):
    """
    Search IMDB using a an identifier, return a list of cached search results.
    One of `search_name`, `imdb_id` or `zap2it_id` is required.
    :param search_name: Name of search to use
    :param imdb_id: Search via IMDB ID
    :param zap2it_id: Search via zap2it ID
    :param force_search: Should search use cache
    :param session: Current DB session
    :return: A List of TVDBSeriesSearchResult objects
    """
    if imdb_id:
        lookup_term = imdb_id
        lookup_url = f'search/series?imdbId={imdb_id}'
    elif zap2it_id:
        lookup_term = zap2it_id
        lookup_url = f'search/series?zap2itId={zap2it_id}'
    elif search_name:
        lookup_term = search_name
        lookup_url = f'search/series?name={search_name}'
    else:
        raise LookupError('not enough parameters for lookup')
    series_search_results = []
    if not force_search:
        logger.debug('trying to fetch TVDB search results from DB')
        series_search_results = (
            session.query(TVDBSeriesSearchResult)
            .filter(TVDBSeriesSearchResult.lookup_term == lookup_term)
            .all()
        )

    if not series_search_results or any(series.expired for series in series_search_results):
        try:
            logger.debug('trying to fetch TVDB search results from TVDB')
            fetched_results = TVDBRequest().get(lookup_url, language=language)
        except requests.RequestException as e:
            raise LookupError(f'Error searching series from TVDb ({e})')
        series_search_results = [
            session.merge(TVDBSeriesSearchResult(series, lookup_term))
            for series in fetched_results
        ]
    if series_search_results:
        return series_search_results
    raise LookupError('No results found for series lookup')


def mark_expired(session):
    """Marks series and episodes that have expired since we cached them"""
    # Only get the expired list every hour
    last_check = persist.get('last_check')

    if not last_check:
        persist['last_check'] = datetime.utcnow()
        return
    if datetime.utcnow() - last_check <= timedelta(hours=2):
        # It has been less than 2 hour, don't check again
        return

    new_last_check = datetime.utcnow()

    try:
        # Calculate seconds since epoch minus a minute for buffer
        last_check_epoch = int((last_check - datetime(1970, 1, 1)).total_seconds()) - 60
        logger.debug('Getting updates from thetvdb ({})', last_check_epoch)
        updates = TVDBRequest().get('updated/query', fromTime=last_check_epoch)
    except requests.RequestException as e:
        logger.error('Could not get update information from tvdb: {}', e)
        return

    expired_series = [series['id'] for series in updates] if updates else []

    # Update our cache to mark the items that have expired
    for chunk in chunked(expired_series):
        series_updated = (
            session.query(TVDBSeries)
            .filter(TVDBSeries.id.in_(chunk))
            .update({'expired': True}, 'fetch')
        )
        episodes_updated = (
            session.query(TVDBEpisode)
            .filter(TVDBEpisode.series_id.in_(chunk))
            .update({'expired': True}, 'fetch')
        )
        logger.debug(
            '{} series and {} episodes marked as expired', series_updated, episodes_updated
        )

    persist['last_check'] = new_last_check
