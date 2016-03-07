from __future__ import unicode_literals, division, absolute_import
import logging
import re
import time
from datetime import datetime, timedelta

from dateutil.parser import parse as dateutil_parse
from sqlalchemy import Table, Column, Integer, String, Unicode, Boolean, Date, DateTime, Time, or_, func, and_
from sqlalchemy.orm import relation, object_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import ForeignKey

from flexget import db_schema
from flexget import plugin
from flexget import options
from flexget.db_schema import upgrade
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.utils import requests
from flexget.utils.database import with_session
from flexget.utils.tools import TimedDict
from flexget.utils.simple_persistence import SimplePersistence
from flexget.logger import console

Base = db_schema.versioned_base('api_trakt', 3)
log = logging.getLogger('api_trakt')
# Production Site
CLIENT_ID = '57e188bcb9750c79ed452e1674925bc6848bd126e02bb15350211be74c6547af'
CLIENT_SECRET = 'db4af7531e8df678b134dbc22445a2c04ebdbdd7213be7f5b6d17dfdfabfcdc2'
API_URL = 'https://api-v2launch.trakt.tv/'
PIN_URL = 'http://trakt.tv/pin/346'
# Stores the last time we checked for updates for shows/movies
updated = SimplePersistence('api_trakt')
LAST_ACTIVITIES_MAP = {
  'all': 'all',
  'movies': {
    'watched_at': 'movies_watched_at',
    'collected_at': 'movies_collected_at',
    'rated_at': 'movies_rated_at',
    'watchlisted_at': 'movied_watchlisted_at',
    'commented_at': 'movies_commented_at',
    'paused_at': 'movies_paused_at'
  },
  'episodes': {
    'watched_at': 'episodes_watched_at',
    'collected_at': 'episodes_collected_at',
    'rated_at': 'episodes_rated_at',
    'watchlisted_at': 'episodes_watchlisted_at',
    'commented_at': 'episodes_commented_at',
    'paused_at': 'episodes_paused_at'
  },
  'shows': {
    'rated_at': 'shows_rated_at',
    'watchlisted_at': 'shows_watchlisted_at',
    'commented_at': 'shows_commented_at'
  },
  'seasons': {
    'rated_at': 'seasons_rated_at',
    'watchlisted_at': 'seasons_watchlisted_at',
    'commented_at': 'seasons_commented_at'
  },
  'comments': {
    'liked_at': 'comments_liked_at'
  },
  'lists': {
    'liked_at': 'lists_liked_at',
    'updated_at': 'lists_updated_at',
    'commented_at': 'lists_commented_at'
  }
}


# Oauth account authentication
class TraktUserAuth(Base):
    __tablename__ = 'trakt_user_auth'

    account = Column(Unicode, primary_key=True)
    access_token = Column(Unicode)
    refresh_token = Column(Unicode)
    created = Column(DateTime)
    expires = Column(DateTime)

    def __init__(self, account, access_token, refresh_token, created, expires):
        self.account = account
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires = token_expire_date(expires)
        self.created = token_created_date(created)


def token_expire_date(expires):
    return datetime.now() + timedelta(seconds=expires)


def token_created_date(created):
    return datetime.fromtimestamp(created)


def device_auth():
    data = {'client_id': CLIENT_ID}
    try:
        r = requests.post(get_api_url('oauth/device/code'), data=data).json()
        device_code = r['device_code']
        user_code = r['user_code']
        expires_in = r['expires_in']
        interval = r['interval']

        console('Please visit {0} and authorize Flexget. Your user code is {1}. Your code expires in '
                '{2} minutes.'.format(r['verification_url'], user_code, expires_in / 60.0))

        log.debug('Polling for user authorization.')
        data['code'] = device_code
        data['client_secret'] = CLIENT_SECRET
        end_time = time.time() + expires_in
        console('Waiting...', end='')
        # stop polling after expires_in seconds
        while time.time() < end_time:
            time.sleep(interval)
            polling_request = requests.post(get_api_url('oauth/device/token'), data=data,
                                            raise_status=False)
            if polling_request.status_code == 200:  # success
                return polling_request.json()
            elif polling_request.status_code == 400:  # pending -- waiting for user
                console('...', end='')
            elif polling_request.status_code == 404:  # not found -- invalid device_code
                raise plugin.PluginError('Invalid device code. Open an issue on Github.')
            elif polling_request.status_code == 409:  # already used -- user already approved
                raise plugin.PluginError('User code has already been approved.')
            elif polling_request.status_code == 410:  # expired -- restart process
                break
            elif polling_request.status_code == 418:  # denied -- user denied code
                raise plugin.PluginError('User code has been denied.')
            elif polling_request.status_code == 429:  # polling too fast
                log.warning('Polling too quickly. Upping the interval. No action required.')
                interval += 1
        raise plugin.PluginError('User code has expired. Please try again.')
    except requests.RequestException as e:
        raise plugin.PluginError('Device authorization with Trakt.tv failed: {0}'.format(e.args[0]))


def token_auth(data):
    try:
        return requests.post(get_api_url('oauth/token'), data=data).json()
    except requests.RequestException as e:
        raise plugin.PluginError('Token exchange with trakt failed: {0}'.format(e.args[0]))


def get_access_token(account, token=None, refresh=False, re_auth=False):
    """
    Gets authorization info from a pin or refresh token.

    :param account: Arbitrary account name to attach authorization to.
    :param unicode token: The pin or refresh token, as supplied by the trakt website.
    :param bool refresh: If True, refresh the access token using refresh_token from db.
    :param bool re_auth: If True, account is re-authorized even if it already exists in db.
    :raises RequestException: If there is a network error while authorizing.
    """
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    with Session() as session:
        acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == account).first()
        if acc and datetime.now() < acc.expires and not refresh and not re_auth:
            return acc.access_token
        else:
            if acc and (refresh or datetime.now() >= acc.expires) and not re_auth:
                log.debug('Using refresh token to re-authorize account %s.', account)
                data['refresh_token'] = acc.refresh_token
                data['grant_type'] = 'refresh_token'
                token_dict = token_auth(data)
            elif token:
                # We are only in here if a pin was specified, so it's safe to use console instead of logging
                console('Warning: PIN authorization has been deprecated. Use Device Authorization instead.')
                data['code'] = token
                data['grant_type'] = 'authorization_code'
                data['redirect_uri'] = 'urn:ietf:wg:oauth:2.0:oob'
                token_dict = token_auth(data)
            else:
                log.debug('No pin specified for an unknown account %s. Attempting to authorize device.', account)
                token_dict = device_auth()
            try:
                access_token = token_dict['access_token']
                refresh_token = token_dict['refresh_token']
                created_at = token_dict.get('created_at', time.time())
                expires_in = token_dict['expires_in']
                if acc:
                    acc.access_token = access_token
                    acc.refresh_token = refresh_token
                    acc.created = token_created_date(created_at)
                    acc.expires = token_expire_date(expires_in)
                else:
                    acc = TraktUserAuth(account, access_token, refresh_token, created_at,
                                        expires_in)
                    session.add(acc)
                return access_token
            except requests.RequestException as e:
                raise plugin.PluginError('Token exchange with trakt failed: {0}'.format(e.args[0]))


def make_list_slug(name):
    """Return the slug for use in url for given list name."""
    slug = name.lower()
    # These characters are just stripped in the url
    for char in '!@#$%^*()[]{}/=?+\\|':
        slug = slug.replace(char, '')
    # These characters get replaced
    slug = slug.replace('&', 'and')
    slug = slug.replace(' ', '-')
    return slug


def get_session(account=None, token=None):
    """
    Creates a requests session ready to talk to trakt API with FlexGet's api key.
    Can also add user level authentication if `account` parameter is given.

    :param account: An account authorized via `flexget trakt auth` CLI command. If given, returned session will be
        authenticated for that account.
    """
    # default to username if account name is not specified
    session = requests.Session()
    session.headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': 2,
        'trakt-api-key': CLIENT_ID,
    }
    if account:
        access_token = get_access_token(account, token) if account else None
        if access_token:
            session.headers.update({'Authorization': 'Bearer %s' % access_token})
    return session


def get_api_url(*endpoint):
    """
    Get the address of a trakt API endpoint.

    :param endpoint: Can by a string endpoint (e.g. 'sync/watchlist') or an iterable (e.g. ('sync', 'watchlist')
        Multiple parameters can also be specified instead of a single iterable.
    :returns: The absolute url to the specified API endpoint.
    """
    if len(endpoint) == 1 and not isinstance(endpoint[0], basestring):
        endpoint = endpoint[0]
    # Make sure integer portions are turned into strings first too
    url = API_URL + '/'.join(map(unicode, endpoint))
    return url


@upgrade('api_trakt')
def upgrade_database(ver, session):
    if ver <= 2:
        raise db_schema.UpgradeImpossible
    return ver


def get_entry_ids(entry):
    """Creates a trakt ids dict from id fields on an entry. Prefers already populated info over lazy lookups."""
    ids = {}
    for lazy in [False, True]:
        if entry.get('trakt_movie_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_movie_id']
        elif entry.get('trakt_show_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_show_id']
        elif entry.get('trakt_episode_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_episode_id']
        if entry.get('tmdb_id', eval_lazy=lazy):
            ids['tmdb'] = entry['tmdb_id']
        if entry.get('tvdb_id', eval_lazy=lazy):
            ids['tvdb'] = entry['tvdb_id']
        if entry.get('imdb_id', eval_lazy=lazy):
            ids['imdb'] = entry['imdb_id']
        if entry.get('tvrage_id', eval_lazy=lazy):
            ids['tvrage'] = entry['tvrage_id']
        if ids:
            break
    return ids


class TraktGenre(Base):

    __tablename__ = 'trakt_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode)

show_genres_table = Table('trakt_show_genres', Base.metadata,
                          Column('show_id', Integer, ForeignKey('trakt_shows.id')),
                          Column('genre_id', Integer, ForeignKey('trakt_genres.id')))
Base.register_table(show_genres_table)

movie_genres_table = Table('trakt_movie_genres', Base.metadata,
                           Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
                           Column('genre_id', Integer, ForeignKey('trakt_genres.id')))
Base.register_table(movie_genres_table)


def get_db_genres(genres, session):
    """Takes a list of genres as strings, returns the database instances for them."""
    db_genres = []
    for genre in genres:
        genre = genre.replace('-', ' ')
        db_genre = session.query(TraktGenre).filter(TraktGenre.name == genre).first()
        if not db_genre:
            db_genre = TraktGenre(name=genre)
            session.add(db_genre)
        db_genres.append(db_genre)
    return db_genres


class TraktActor(Base):

    __tablename__ = 'trakt_actors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode, nullable=False)
    imdb_id = Column(Unicode)
    trakt_id = Column(Unicode)
    tmdb_id = Column(Unicode)

    def __init__(self, name, trakt_id, imdb_id=None, tmdb_id=None):
        self.name = name
        self.trakt_id = trakt_id
        self.imdb_id = imdb_id
        self.tmdb_id = tmdb_id


show_actors_table = Table('trakt_show_actors', Base.metadata,
                          Column('show_id', Integer, ForeignKey('trakt_shows.id')),
                          Column('actors_id', Integer, ForeignKey('trakt_actors.id')))
Base.register_table(show_actors_table)

movie_actors_table = Table('trakt_movie_actors', Base.metadata,
                           Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
                           Column('actors_id', Integer, ForeignKey('trakt_actors.id')))
Base.register_table(movie_actors_table)


def get_db_actors(id, style):
    actors = []
    url = get_api_url(style + 's', id, 'people')
    req_session = get_session()
    try:
        results = req_session.get(url).json()
        with Session() as session:
            for result in results.get('cast'):
                name = result.get('person').get('name')
                ids = result.get('person').get('ids')
                trakt_id = ids.get('trakt')
                imdb_id = ids.get('imdb')
                tmdb_id = ids.get('tmdb')
                actor = session.query(TraktActor).filter(TraktActor.trakt_id == trakt_id).first()
                if not actor:
                    actor = TraktActor(name, trakt_id, imdb_id, tmdb_id)
                actors.append(actor)
        return actors
    except requests.RequestException as e:
        log.debug('Error searching for actors for trakt id %s' % e)
        return


def list_actors(actors):
    res = {}
    for actor in actors:
        info = {}
        info['name'] = actor.name
        info['imdb_id'] = str(actor.imdb_id)
        info['tmdb_id'] = str(actor.tmdb_id)
        res[str(actor.trakt_id)] = info
    return res


class TraktEpisode(Base):
    __tablename__ = 'trakt_episodes'

    id = Column(Integer, primary_key=True, autoincrement=False)
    tvdb_id = Column(Integer)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    title = Column(Unicode)
    season = Column(Integer)
    number = Column(Integer)
    number_abs = Column(Integer)
    overview = Column(Unicode)
    first_aired = Column(DateTime)
    updated_at = Column(DateTime)
    cached_at = Column(DateTime)

    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=False)

    def __init__(self, trakt_episode):
        super(TraktEpisode, self).__init__()
        self.update(trakt_episode)

    def update(self, trakt_episode):
        """Updates this record from the trakt media object `trakt_movie` returned by the trakt api."""
        if self.id and self.id != trakt_episode['ids']['trakt']:
            raise Exception('Tried to update db ep with different ep data')
        elif not self.id:
            self.id = trakt_episode['ids']['trakt']
        self.imdb_id = trakt_episode['ids']['imdb']
        self.tmdb_id = trakt_episode['ids']['tmdb']
        self.tvrage_id = trakt_episode['ids']['tvrage']
        self.tvdb_id = trakt_episode['ids']['tvdb']
        self.first_aired = None
        if trakt_episode.get('first_aired'):
            self.first_aired = dateutil_parse(trakt_episode['first_aired'], ignoretz=True)
        self.updated_at = dateutil_parse(trakt_episode.get('updated_at'), ignoretz=True)
        self.cached_at = datetime.now()

        for col in ['title', 'season', 'number', 'number_abs', 'overview']:
            setattr(self, col, trakt_episode.get(col))

    @property
    def expired(self):
        # TODO should episode have its own expiration function?
        return False


class TraktShow(Base):
    __tablename__ = 'trakt_shows'

    id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(Unicode)
    year = Column(Integer)
    slug = Column(Unicode)
    tvdb_id = Column(Integer)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    overview = Column(Unicode)
    first_aired = Column(DateTime)
    air_day = Column(Unicode)
    air_time = Column(Time)
    runtime = Column(Integer)
    certification = Column(Unicode)
    network = Column(Unicode)
    country = Column(Unicode)
    status = Column(String)
    rating = Column(Integer)
    votes = Column(Integer)
    language = Column(Unicode)
    aired_episodes = Column(Integer)
    episodes = relation(TraktEpisode, backref='show', cascade='all, delete, delete-orphan', lazy='dynamic')
    genres = relation(TraktGenre, secondary=show_genres_table)
    _actors = relation(TraktActor, secondary=show_actors_table)
    updated_at = Column(DateTime)
    cached_at = Column(DateTime)

    def __init__(self, trakt_show, session):
        super(TraktShow, self).__init__()
        self.update(trakt_show, session)

    def update(self, trakt_show, session):
        """Updates this record from the trakt media object `trakt_show` returned by the trakt api."""
        if self.id and self.id != trakt_show['ids']['trakt']:
            raise Exception('Tried to update db show with different show data')
        elif not self.id:
            self.id = trakt_show['ids']['trakt']
        self.slug = trakt_show['ids']['slug']
        self.imdb_id = trakt_show['ids']['imdb']
        self.tmdb_id = trakt_show['ids']['tmdb']
        self.tvrage_id = trakt_show['ids']['tvrage']
        self.tvdb_id = trakt_show['ids']['tvdb']
        if trakt_show.get('air_time'):
            self.air_time = dateutil_parse(trakt_show.get('air_time'), ignoretz=True)
        else:
            self.air_time = None
        if trakt_show.get('first_aired'):
            self.first_aired = dateutil_parse(trakt_show.get('first_aired'), ignoretz=True)
        else:
            self.first_aired = None
        self.updated_at = dateutil_parse(trakt_show.get('updated_at'), ignoretz=True)

        for col in ['overview', 'runtime', 'rating', 'votes', 'language', 'title', 'year', 'air_day',
                    'runtime', 'certification', 'network', 'country', 'status', 'aired_episodes']:
            setattr(self, col, trakt_show.get(col))

        self.genres[:] = get_db_genres(trakt_show.get('genres', []), session)
        self.cached_at = datetime.now()

    def get_episode(self, season, number, only_cached=False):
        # TODO: Does series data being expired mean all episode data should be refreshed?
        episode = self.episodes.filter(TraktEpisode.season == season).filter(TraktEpisode.number == number).first()
        if not episode or self.expired:
            url = get_api_url('shows', self.id, 'seasons', season, 'episodes', number, '?extended=full')
            if only_cached:
                raise LookupError('Episode %s %s not found in cache' % (season, number))
            log.debug('Episode %s %s not found in cache, looking up from trakt.' % (season, number))
            try:
                ses = get_session()
                data = ses.get(url).json()
            except requests.RequestException:
                raise LookupError('Error Retrieving Trakt url: %s' % url)
            if not data:
                raise LookupError('No data in response from trakt %s' % url)
            episode = self.episodes.filter(TraktEpisode.id == data['ids']['trakt']).first()
            if episode:
                episode.update(data)
            else:
                episode = TraktEpisode(data)
                self.episodes.append(episode)
        return episode

    @property
    def expired(self):
        """
        :return: True if show details are considered to be expired, ie. need of update
        """
        # TODO stolen from imdb plugin, maybe there's a better way?
        if self.cached_at is None:
            log.debug('cached_at is None: %s' % self)
            return True
        refresh_interval = 2
        # if show has been cancelled or ended, then it is unlikely to be updated often
        if self.year and (self.status == 'ended' or self.status == 'canceled'):
            # Make sure age is not negative
            age = max((datetime.now().year - self.year), 0)
            refresh_interval += age * 5
            log.debug('show `%s` age %i expires in %i days' % (self.title, age, refresh_interval))
        return self.cached_at < datetime.now() - timedelta(days=refresh_interval)

    @property
    def actors(self):
        if not self._actors:
            self._actors[:] = get_db_actors(self.id, 'show')
        return self._actors

    def __repr__(self):
        return '<name=%s, id=%s>' % (self.title, self.id)


class TraktMovie(Base):
    __tablename__ = 'trakt_movies'

    id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(Unicode)
    year = Column(Integer)
    slug = Column(Unicode)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tagline = Column(Unicode)
    overview = Column(Unicode)
    released = Column(Date)
    runtime = Column(Integer)
    rating = Column(Integer)
    votes = Column(Integer)
    language = Column(Unicode)
    updated_at = Column(DateTime)
    cached_at = Column(DateTime)
    genres = relation(TraktGenre, secondary=movie_genres_table)
    _actors = relation(TraktActor, secondary=movie_actors_table)

    def __init__(self, trakt_movie, session):
        super(TraktMovie, self).__init__()
        self.update(trakt_movie, session)

    def update(self, trakt_movie, session):
        """Updates this record from the trakt media object `trakt_movie` returned by the trakt api."""
        if self.id and self.id != trakt_movie['ids']['trakt']:
            raise Exception('Tried to update db movie with different movie data')
        elif not self.id:
            self.id = trakt_movie['ids']['trakt']
        self.slug = trakt_movie['ids']['slug']
        self.imdb_id = trakt_movie['ids']['imdb']
        self.tmdb_id = trakt_movie['ids']['tmdb']
        for col in ['title', 'overview', 'runtime', 'rating', 'votes', 'language', 'tagline', 'year']:
            setattr(self, col, trakt_movie.get(col))
        if self.released:
            self.released = dateutil_parse(trakt_movie.get('released'), ignoretz=True)
        self.updated_at = dateutil_parse(trakt_movie.get('updated_at'), ignoretz=True)
        self.genres[:] = get_db_genres(trakt_movie.get('genres', []), session)
        self.cached_at = datetime.now()

    @property
    def expired(self):
        """
        :return: True if movie details are considered to be expired, ie. need of update
        """
        # TODO stolen from imdb plugin, maybe there's a better way?
        if self.updated_at is None:
            log.debug('updated_at is None: %s' % self)
            return True
        refresh_interval = 2
        if self.year:
            # Make sure age is not negative
            age = max((datetime.now().year - self.year), 0)
            refresh_interval += age * 5
            log.debug('movie `%s` age %i expires in %i days' % (self.title, age, refresh_interval))
        return self.cached_at < datetime.now() - timedelta(days=refresh_interval)

    @property
    def actors(self):
        if not self._actors:
            self._actors[:] = get_db_actors(self.id, 'movie')
        return self._actors


class TraktShowSearchResult(Base):

    __tablename__ = 'trakt_show_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, unique=True, nullable=False)
    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=True)
    series = relation(TraktShow, backref='search_strings')


class TraktMovieSearchResult(Base):

    __tablename__ = 'trakt_movie_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, unique=True, nullable=False)
    movie_id = Column(Integer, ForeignKey('trakt_movies.id'), nullable=True)
    movie = relation(TraktMovie, backref='search_strings')


def split_title_year(title):
    """Splits title containing a year into a title, year pair."""
    # We only recognize years from the 2nd and 3rd millennium, FlexGetters from the year 3000 be damned!
    match = re.search(r'[\s(]([12]\d{3})\)?$', title)
    if match:
        title = title[:match.start()].strip()
        year = int(match.group(1))
    else:
        year = None
    return title, year


@with_session
def get_cached(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None,
               tvdb_id=None, tvrage_id=None, session=None):
    """
    Get the cached info for a given show/movie from the database.

    :param type: Either 'show' or 'movie'
    """
    ids = {
        'id': trakt_id,
        'slug': trakt_slug,
        'tmdb_id': tmdb_id,
        'imdb_id': imdb_id,
    }
    if style == 'show':
        ids['tvdb_id'] = tvdb_id
        ids['tvrage_id'] = tvrage_id
        model = TraktShow
    else:
        model = TraktMovie
    result = None
    if any(ids.values()):
        result = session.query(model).filter(
            or_(getattr(model, col) == val for col, val in ids.iteritems() if val)).first()
    elif title:
        title, y = split_title_year(title)
        year = year or y
        query = session.query(model).filter(model.title == title)
        if year:
            query = query.filter(model.year == year)
        result = query.first()
    return result


def get_trakt(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None,
              tvdb_id=None, tvrage_id=None):
    """Returns the matching media object from trakt api."""
    # TODO: Better error messages
    # Trakt api accepts either id or slug (there is a rare possibility for conflict though, e.g. 24)
    trakt_id = trakt_id or trakt_slug
    req_session = get_session()
    last_search_query = None  # used if no results are found
    last_search_type = None
    if not trakt_id:
        # Try finding trakt_id based on other ids
        ids = {
            'imdb': imdb_id,
            'tmdb': tmdb_id
        }
        if style == 'show':
            ids['tvdb'] = tvdb_id
            ids['tvrage'] = tvrage_id
        for id_type, identifier in ids.iteritems():
            if not identifier:
                continue
            try:
                last_search_query = identifier
                last_search_type = id_type
                results = req_session.get(get_api_url('search'), params={'id_type': id_type, 'id': identifier}).json()
            except requests.RequestException as e:
                log.debug('Error searching for trakt id %s' % e)
                continue
            for result in results:
                if result['type'] != style:
                    continue
                trakt_id = result[style]['ids']['trakt']
                break
            if trakt_id:
                break
        if not trakt_id and title:
            last_search_query = title
            last_search_type = 'title'
            # Try finding trakt id based on title and year
            if style == 'show':
                parsed_title, y = split_title_year(title)
                y = year or y
            else:
                title_parser = get_plugin_by_name('parsing').instance.parse_movie(title)
                y = year or title_parser.year
                parsed_title = title_parser.name
            try:
                results = req_session.get(get_api_url('search'), params={'query': parsed_title, 'type': style,
                                                                         'year': y}).json()
            except requests.RequestException as e:
                raise LookupError('Searching trakt for %s failed with error: %s' % (title, e))
            for result in results:
                if year and result[style]['year'] != year:
                    continue
                if parsed_title.lower() == result[style]['title'].lower():
                    trakt_id = result[style]['ids']['trakt']
                    break
            # grab the first result if there is no exact match
            if not trakt_id and results and results[0]['score'] >= 34:
                trakt_id = results[0][style]['ids']['trakt']
    if not trakt_id:
        raise LookupError('Unable to find %s="%s" on trakt.' % (last_search_type, last_search_query))
    # Get actual data from trakt
    try:
        return req_session.get(get_api_url(style + 's', trakt_id), params={'extended': 'full'}).json()
    except requests.RequestException as e:
        raise LookupError('Error getting trakt data for id %s: %s' % (trakt_id, e))


class TraktMovieUserActivity(Base):
    __tablename__ = 'trakt_movie_user_activity'
    id = Column(Integer, primary_key=True)
    movie = relation(TraktMovie, backref='user_activity')
    movie_id = Column(Integer, ForeignKey('trakt_movies.id'), nullable=True)
    collected_at = Column(DateTime, nullable=True)
    watched_at = Column(DateTime, nullable=True)
    account = Column(Unicode, nullable=False)


class TraktEpisodeUserActivity(Base):
    __tablename__ = 'trakt_episode_user_activity'
    id = Column(Integer, primary_key=True)
    episode = relation(TraktEpisode, backref='user_activity')
    episode_id = Column(Integer, ForeignKey('trakt_episodes.id'), nullable=True)
    collected_at = Column(DateTime, nullable=True)
    watched_at = Column(DateTime, nullable=True)
    account = Column(Unicode, nullable=False)


class TraktLastActivities(Base):

    __tablename__ = 'trakt_last_activities'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    last_activity = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    account = Column(Unicode, nullable=False)

    def __init__(self, name, last_activity, account, updated_at=None):
        self.name = name
        self.last_activity = dateutil_parse(last_activity, ignoretz=True)
        if updated_at:
            self.updated_at = dateutil_parse(updated_at, ignoretz=True)
        self.account = account

    def update(self, last_activity, updated_at=None):
        self.last_activity = dateutil_parse(last_activity, ignoretz=True)
        if updated_at:
            self.updated_at = dateutil_parse(updated_at, ignoretz=True)


@with_session
def get_last_activities(account, session=None):
    req_session = get_session(account=account)
    try:
        activities = req_session.get(get_api_url('sync/last_activities')).json()
        # update last activities table
        for k, v in activities.iteritems():
            log.error('plssss')
            if isinstance(v, dict):
                for media_type, timestamp in v.iteritems():
                    name = LAST_ACTIVITIES_MAP.get(k, {}).get(media_type)
                    r = session.query(TraktLastActivities).filter_by(name=name, account=account).first()
                    if r and r.last_activity != dateutil_parse(timestamp, ignoretz=True):
                        r.update(timestamp)
                    elif not r:
                        session.add(TraktLastActivities(name, timestamp, account))
                        session.commit()
            else:
                name = LAST_ACTIVITIES_MAP.get(k)
                r = session.query(TraktLastActivities).filter_by(name=name, account=account).first()
                if r and r.last_activity != dateutil_parse(v, ignoretz=True):
                        r.update(v)
                elif not r:
                    session.add(TraktLastActivities(name, v, account))
                    session.commit()
        ApiTrakt.sync_cache['last_activities'] = True
    except requests.RequestException as e:
        raise plugin.PluginError('Getting latest user activity failed: %s', e.args[0])


@with_session
def is_sync_update_required(name, account, session=None):
    # get and update last_activities
    update_required = False
    get_last_activities(account, session=session)
    r = session.query(TraktLastActivities).filter(and_(TraktLastActivities.name == name,
                                                       TraktLastActivities.account == account)).first()
    if not r:
        raise plugin.PluginError('Last Activity name %s does not exist' % name)
    if r.updated_at and r.last_activity > r.updated_at:
        update_required = True
    elif not r.updated_at:
        update_required = True
    return update_required


@with_session
def update_episode_collection(username=None, account=None, session=None):
    pass


@with_session
def update_movie_collection(username=None, account=None, session=None):
    if account:
        url = get_api_url('sync', 'collection', 'movies')
    else:
        url = get_api_url('users', username, 'collection', 'movies')
    req_session = get_session(account=account)
    try:
        movies = req_session.get(url).json()
        if not movies:
            log.warning('No movie collection data returned from trakt.')
            return
        log.verbose('Received %d records from trakt.tv collection associated with account %s', len(movies),
                    account)
        if account:  # update DB
            for movie in movies:
                collected_at = dateutil_parse(movie['collected_at'], ignoretz=True)
                r = session.query(TraktMovieUserActivity).filter(TraktMovieUserActivity.movie_id ==
                                                                 movie['movie']['ids']['trakt']).first()
                if r:
                    r.collected_at = collected_at
                else:
                    lookupargs = {'title': movie['movie']['title'],
                                  'year':  movie['movie']['year'],
                                  'trakt_id': movie['movie']['ids']['trakt'],
                                  'trakt_slug': movie['movie']['ids']['slug'],
                                  'tmdb_id': movie['movie']['ids']['tmdb'],
                                  'imdb_id': movie['movie']['ids']['imdb']}
                    cached_movie = get_cached('movie', session=session, **lookupargs)
                    if not cached_movie:
                        log.debug('Collected movie with trakt id %s not found in lookup cache',
                                  movie['movie']['ids']['trakt'])
                        movie['movie']['updated_at'] = unicode(datetime.now())
                        cached_movie = TraktMovie(movie['movie'], session=session)
                        session.add(cached_movie)
                    collected = TraktMovieUserActivity(movie=cached_movie, collected_at=collected_at,
                                                       account=account)
                    session.add(collected)
        else:  # update local cache
            ApiTrakt.sync_cache[username] = {}
            for movie in movies:
                movie_id = movie['movie']['ids']['trakt']
                ApiTrakt.sync_cache[username][movie_id] = movie['movie']
                ApiTrakt.sync_cache[username][movie_id]['collected_at'] = dateutil_parse(movie['collected_at'],
                                                                                         ignoretz=True)

    except requests.RequestException as e:
        raise plugin.PluginError('Unable to get movie collection data from trakt.tv: %s' % e)


class ApiTrakt(object):

    sync_cache = TimedDict(cache_time='15 minutes')

    @staticmethod
    @with_session
    def lookup_series(session=None, only_cached=None, **lookup_params):
        series = get_cached('show', session=session, **lookup_params)
        title = lookup_params.get('title', '')
        found = None
        if not series and title:
            found = session.query(TraktShowSearchResult).filter(func.lower(TraktShowSearchResult.search) ==
                                                                title.lower()).first()
            if found and found.series:
                log.debug('Found %s in previous search results as %s' % (title, found.series.title))
                series = found.series
        if only_cached:
            if series:
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            return series
        try:
            trakt_show = get_trakt('show', **lookup_params)
        except LookupError as e:
            if series:
                log.debug('Error refreshing show data from trakt, using cached. %s' % e)
                return series
            raise
        series = session.query(TraktShow).filter(TraktShow.id == trakt_show['ids']['trakt']).first()
        if series:
            series.update(trakt_show, session)
        else:
            series = TraktShow(trakt_show, session)
            session.add(series)
        if series and title.lower() == series.title.lower():
            return series
        elif series and not found:
            if not session.query(TraktShowSearchResult).filter(func.lower(TraktShowSearchResult.search) ==
                                                               title.lower()).first():
                log.debug('Adding search result to db')
                session.add(TraktShowSearchResult(search=title, series=series))
        elif series and found:
            log.debug('Updating search result in db')
            found.series = series
        return series

    @staticmethod
    @with_session
    def lookup_movie(session=None, only_cached=None, **lookup_params):
        movie = get_cached('movie', session=session, **lookup_params)
        title = lookup_params.get('title', '')
        found = None
        if not movie and title:
            found = session.query(TraktMovieSearchResult).filter(func.lower(TraktMovieSearchResult.search) ==
                                                                 title.lower()).first()
            if found and found.movie:
                log.debug('Found %s in previous search results as %s' % (title, found.movie.title))
                movie = found.movie
        if only_cached:
            if movie:
                return movie
            raise LookupError('Movie %s not found from cache' % lookup_params)
        if movie and not movie.expired:
            return movie
        try:
            trakt_movie = get_trakt('movie', **lookup_params)
        except LookupError as e:
            if movie:
                log.debug('Error refreshing movie data from trakt, using cached. %s' % e)
                return movie
            raise
        movie = session.query(TraktMovie).filter(TraktMovie.id == trakt_movie['ids']['trakt']).first()
        if movie:
            movie.update(trakt_movie, session)
        else:
            movie = TraktMovie(trakt_movie, session)
            session.add(movie)
        if movie and title.lower() == movie.title.lower():
            return movie
        if movie and not found:
            if not session.query(TraktMovieSearchResult).filter(func.lower(TraktMovieSearchResult.search) ==
                                                                title.lower()).first():
                log.debug('Adding search result to db')
                session.add(TraktMovieSearchResult(search=title, movie=movie))
        elif movie and found:
            log.debug('Updating search result in db')
            found.movie = movie
        return movie

    @staticmethod
    @with_session
    def collected(style, trakt_data, title, account=None, username=None, session=None):
        media_type = style + 's'
        in_collection = False
        if account and not username:
            last_activities_name = LAST_ACTIVITIES_MAP[media_type]['collected_at']
            if not ApiTrakt.sync_cache.get('last_activities') and \
                    is_sync_update_required(last_activities_name, account, session=session):
                if media_type == 'movies':
                    update_movie_collection(account=account, session=session)
                if media_type == 'shows':
                    update_episode_collection(account=account, session=session)
            # FETCH FROM DB
            if media_type == 'movies':
                r = session.query(TraktMovieUserActivity).filter(TraktMovieUserActivity.movie_id ==
                                                                 trakt_data.id).first()
            else:
                r = session.query(TraktEpisodeUserActivity).filter(TraktEpisodeUserActivity.episode_id ==
                                                                   trakt_data.id).first()
            in_collection = True if r else False
        else:  # NO DB, JUST TIMEDDICT
            if username not in ApiTrakt.sync_cache:
                update_movie_collection(username=username)
            if trakt_data.id in ApiTrakt.sync_cache.get(username):
                in_collection = True
        log.info('The result for entry "%s" is: %s' % (title,
                 'Owned' if in_collection else 'Not owned'))
        return in_collection

    @staticmethod
    def watched(username, style, trakt_data, title, account=None):
        url = get_api_url('users', username, 'history', style + 's', trakt_data.id)
        session = get_session(account=account)
        try:
            log.debug('Opening %s' % url)
            data = session.get(url).json()
        except requests.RequestException as e:
            raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)

        if not data:
            log.warning('No data returned from trakt.')
            return
        log.verbose('Received %d records from trakt.tv %s\'s history' % (len(data), username))
        watched = False
        if style == 'episode':
            for ep in data:
                if trakt_data.show.id == ep['show']['ids']['trakt']:
                    ep_data = ep['episode']
                    if ep_data['season'] == trakt_data.season and ep_data['number'] == trakt_data.number:
                        watched = True
                        break
                    log.debug('The result for entry "%s" is: %s' % (title,
                              'Watched' if watched else 'Not watched'))
        else:
            for movie in data:
                if trakt_data.id == movie['movie']['ids']['trakt']:
                    watched = True
                    break
            log.debug('The result for entry "%s" is: %s' % (title,
                      'Watched' if watched else 'Not watched'))
        return watched


def delete_account(account):
    with Session() as session:
        acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == account).first()
        if not acc:
            raise plugin.PluginError('Account %s not found.' % account)
        session.delete(acc)


def do_cli(manager, options):
    if options.action == 'auth':
        if not (options.account):
            console('You must specify an account (local identifier) so we know where to save your access token!')
            return
        try:
            get_access_token(options.account, options.pin, re_auth=True)
            console('Successfully authorized Flexget app on Trakt.tv. Enjoy!')
            return
        except plugin.PluginError as e:
            console('Authorization failed: %s' % e)
    elif options.action == 'show':
        with Session() as session:
            if not options.account:
                # Print all accounts
                accounts = session.query(TraktUserAuth).all()
                if not accounts:
                    console('No trakt authorizations stored in database.')
                    return
                console('{:-^21}|{:-^28}|{:-^28}'.format('Account', 'Created', 'Expires'))
                for auth in accounts:
                    console('{:<21}|{:>28}|{:>28}'.format(
                        auth.account, auth.created.strftime('%Y-%m-%d'), auth.expires.strftime('%Y-%m-%d')))
                return
            # Show a specific account
            acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == options.account).first()
            if acc:
                console('Authorization expires on %s' % acc.expires)
            else:
                console('Flexget has not been authorized to access your account.')
    elif options.action == 'refresh':
        if not options.account:
            console('Please specify an account')
            return
        try:
            get_access_token(options.account, refresh=True)
            console('Successfully refreshed your access token.')
            return
        except plugin.PluginError as e:
            console('Authorization failed: %s' % e)
    elif options.action == 'delete':
        if not options.account:
            console('Please specify an account')
            return
        try:
            delete_account(options.account)
            console('Successfully deleted your access token.')
            return
        except plugin.PluginError as e:
            console('Deletion failed: %s' % e)


@event('options.register')
def register_parser_arguments():
    acc_text = 'local identifier which should be used in your config to refer these credentials'
    # Register subcommand
    parser = options.register_command('trakt', do_cli, help='view and manage trakt authentication.')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')
    auth_parser = subparsers.add_parser('auth', help='authorize Flexget to access your Trakt.tv account')

    auth_parser.add_argument('account', metavar='<account>', help=acc_text)
    auth_parser.add_argument('pin', metavar='<pin>', help='get this by authorizing FlexGet to use your trakt account '
                                                          'at %s' % PIN_URL, nargs='?')

    show_parser = subparsers.add_parser('show', help='show expiration date for Flexget authorization(s) (don\'t worry, '
                                                     'they will automatically refresh when expired)')

    show_parser.add_argument('account', metavar='<account>', nargs='?', help=acc_text)

    refresh_parser = subparsers.add_parser('refresh', help='manually refresh your access token associated with your'
                                                           ' --account <name>')

    refresh_parser.add_argument('account', metavar='<account>', help=acc_text)

    delete_parser = subparsers.add_parser('delete', help='delete the specified <account> name from local database')

    delete_parser.add_argument('account', metavar='<account>', help=acc_text)


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTrakt, 'api_trakt', api_ver=2)
