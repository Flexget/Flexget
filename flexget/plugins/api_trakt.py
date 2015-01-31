from __future__ import unicode_literals, division, absolute_import
from difflib import SequenceMatcher
import logging
from urlparse import urljoin

from dateutil.parser import parse as dateutil_parse
from sqlalchemy import Table, Column, Integer, String, Unicode, Boolean, func, Date, DateTime, Time, or_
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema
from flexget import plugin
from flexget.db_schema import upgrade
from flexget.event import event
from flexget.plugins.filter.series import normalize_series_name
from flexget.utils import json, requests
from flexget.utils.database import with_session
from flexget.utils.simple_persistence import SimplePersistence

api_key = '6c228565a45a302e49fb7d2dab066c9ab948b7be/'
search_show = 'http://api.trakt.tv/search/shows.json/'
episode_summary = 'http://api.trakt.tv/show/episode/summary.json/'
show_summary = 'http://api.trakt.tv/show/summary.json/'
Base = db_schema.versioned_base('api_trakt', 3)
log = logging.getLogger('api_trakt')
# Production Site
API_KEY = '57e188bcb9750c79ed452e1674925bc6848bd126e02bb15350211be74c6547af'
API_URL = 'https://api.trakt.tv/'

# Stores the last time we checked for updates for shows/movies
updated = SimplePersistence('api_trakt')


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


def get_session(username=None, password=None):
    """Creates a requests session which is authenticated to trakt."""
    session = requests.Session()
    session.headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': 2,
        'trakt-api-key': API_KEY
    }
    if username:
        session.headers['trakt-user-login'] = username
    if username and password:
        auth = {'login': username, 'password': password}
        try:
            r = session.post(urljoin(API_URL, 'auth/login'), data=json.dumps(auth))
        except requests.RequestException as e:
            if e.response and e.response.status_code in [401, 403]:
                raise plugin.PluginError('Authentication to trakt failed, check your username/password: %s' % e.args[0])
            else:
                raise plugin.PluginError('Authentication to trakt failed: %s' % e.args[0])
        try:
            session.headers['trakt-user-token'] = r.json()['token']
        except (ValueError, KeyError):
            raise plugin.PluginError('Got unexpected response content while authorizing to trakt: %s' % r.text)
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
    if ver <=2:
        pass  # TODO: Clear out all old db
    return ver


@with_session
def mark_expired(type, session=None):
    """
    Mark which cached shows/movies have updated information on trakt.

    :param type: Either 'shows' or 'movies'
    """
    # TODO: Implement


class TraktGenre(Base):

    __tablename__ = 'trakt_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode)
    slug = Column(Unicode) # Not sure if this is needed, depends on what is returned by genres from api calls

show_genres_table = Table('trakt_show_genres', Base.metadata,
                         Column('show_id', Integer, ForeignKey('trakt_shows.id')),
                         Column('genre_id', Integer, ForeignKey('trakt_genres.id')))

movie_genres_table = Table('trakt_movie_genres', Base.metadata,
                          Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
                          Column('genre_id', Integer, ForeignKey('trakt_genres.id')))


class TraktActor(Base):

    __tablename__ = 'trakt_actors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)


show_actors_table = Table('trakt_show_actors', Base.metadata,
                     Column('show_id', Integer, ForeignKey('trakt_shows.id')),
                     Column('actors_id', Integer, ForeignKey('trakt_actors.id')))

movie_actors_table = Table('trakt_movie_actors', Base.metadata,
                     Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
                     Column('actors_id', Integer, ForeignKey('trakt_actors.id')))


class TraktEpisode(Base):
    __tablename__ = 'trakt_episodes'

    id = Column(Integer, primary_key=True, autoincrement=False)
    slug = Column(Unicode)
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
    expired = Column(Boolean)
    updated_at = Column(DateTime)

    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=False)

    def update(self, trakt_episode):
        """Updates this record from the trakt media object `trakt_movie` returned by the trakt api."""
        if self.id and self.id != trakt_episode['ids']['trakt']:
            raise Exception('Tried to update db movie with different movie data')
        elif not self.id:
            self.id = trakt_episode['ids']['trakt']
        self.slug = trakt_episode['ids']['slug']
        self.imdb_id = trakt_episode['ids']['imdb']
        self.tmdb_id = trakt_episode['ids']['tmdb']
        self.tvrage_id = trakt_episode['ids']['tvrage']
        self.tvdb_id = trakt_episode['ids']['tvdb']
        self.first_aired = dateutil_parse(trakt_episode.get('first_aired'))
        self.updated_at = dateutil_parse(trakt_episode.get('updated_at'))

        for col in ['title', 'season', 'number', 'number_abs', 'overview']:
            setattr(self, col, trakt_episode.get(col))

        for genre in trakt_episode.get('genres', ()):
            # TODO: the stuff
            pass
        self.expired = False


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
    #episodes = relation(TraktEpisode, backref='show', cascade='all, delete, delete-orphan')
    #genres = relation(TraktGenre, secondary=show_genres_table)
    #actors = relation(TraktActor, secondary=show_actors_table)
    updated_at = Column(DateTime)
    expired = Column(Boolean)

    def update(self, trakt_show):
        """Updates this record from the trakt media object `trakt_show` returned by the trakt api."""
        if self.id and self.id != trakt_show['ids']['trakt']:
            raise Exception('Tried to update db movie with different movie data')
        elif not self.id:
            self.id = trakt_show['ids']['trakt']
        self.slug = trakt_show['ids']['slug']
        self.imdb_id = trakt_show['ids']['imdb']
        self.tmdb_id = trakt_show['ids']['tmdb']
        self.tvrage_id = trakt_show['ids']['tvrage']
        self.tvdb_id = trakt_show['ids']['tvdb']
        if trakt_show.get('air_time'):
            self.air_time = dateutil_parse(trakt_show.get('air_time'))
        else:
            self.air_time = None
        if trakt_show.get('first_aired'):
            self.first_aired = dateutil_parse(trakt_show.get('first_aired'))
        else:
            self.first_aired = None
        self.updated_at = dateutil_parse(trakt_show.get('updated_at'))

        for col in ['overview', 'runtime', 'rating', 'votes', 'language', 'title', 'year', 'air_day',
                    'runtime', 'certification', 'network', 'country', 'status', 'aired_episodes']:
            setattr(self, col, trakt_show.get(col))

        for genre in trakt_show.get('genres', ()):
            # TODO: the stuff
            pass
        self.expired = False

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
    expired = Column(Boolean)
    updated_at = Column(DateTime)
    genres = relation(TraktGenre, secondary=movie_genres_table)
    _actors = relation(TraktActor, secondary=movie_actors_table)

    def update(self, trakt_movie):
        """Updates this record from the trakt media object `trakt_movie` returned by the trakt api."""
        if self.id and self.id != trakt_movie['ids']['trakt']:
            raise Exception('Tried to update db movie with different movie data')
        elif not self.id:
            self.id = trakt_movie['ids']['trakt']
        self.slug = trakt_movie['ids']['slug']
        self.imdb_id = trakt_movie['ids']['imdb']
        self.tmdb_id = trakt_movie['ids']['tmdb']
        for col in ['overview', 'runtime', 'rating', 'votes', 'language', 'tagline', 'year']:
            setattr(self, col, trakt_movie.get(col))
        self.released = dateutil_parse(trakt_movie.get('released'))
        self.updated_at = dateutil_parse(trakt_movie.get('updated_at'))
        for genre in trakt_movie.get('genres', ()):
            # TODO: the stuff
            pass
        self.expired = False

    @property
    def actors(self):
        if not self._actors:
            # TODO: Update the stuff from trakt
            pass
        return self._actors


class TraktSearchResult(Base):

    __tablename__ = 'trakt_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, nullable=False)
    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=True)
    series = relation(TraktShow, backref='search_strings')


@with_session
def get_cached(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None, tvdb_id=None,
               tvrage_id=None, session=None):
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
        query = session.query(model).filter(model.title == title)
        if year:
            query = query.filter(model.year == year)
        result = query.first()
    return result


def get_trakt(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None, tvdb_id=None,
              tvrage_id=None):
    """Returns the matching media object from trakt api."""
    # TODO: Better error messages
    # Trakt api accepts either id or slug (there is a rare possibility for conflict though, e.g. 24)
    trakt_id = trakt_id or trakt_slug
    req_session = get_session()
    if not trakt_id:
        # Try finding trakt_id based on other ids
        ids = {
            'tmdb': tmdb_id,
            'imdb': imdb_id
        }
        if style == 'show':
            ids['tvdb'] = tvdb_id
            ids['tvrage'] = tvrage_id
        for id_type, identifier in ids.iteritems():
            if not identifier:
                continue
            try:
                results = req_session.get(get_api_url('search'), params={'id_type': id_type, 'id': identifier}).json()
            except requests.RequestException as e:
                log.debug('Error searching for trakt id %s' % e)
                continue
            for result in results:
                if result['type'] != style:
                    raise LookupError('Provided id (%s) is for a %s not a %s' % (identifier, result['type'], style))
                trakt_id = result[style]['ids']['trakt']
                break
        if not trakt_id:
            # Try finding trakt id based on title and year
            clean_title = normalize_series_name(title)
            try:
                results = req_session.get(get_api_url('search'), params={'query': clean_title, 'type': style}).json()
            except requests.RequestException as e:
                raise LookupError('Searching trakt for %s failed with error: %s' % (title, e))
            for result in results:
                if year and result[style]['year'] != year:
                    continue
                if clean_title == normalize_series_name(result[style]['title']):
                    trakt_id = result[style]['ids']['trakt']
                    break
    if not trakt_id:
        raise LookupError('Unable to find %s on trakt.' % type)
    # Get actual data from trakt
    try:
        return req_session.get(get_api_url(style + 's', trakt_id), params={'extended': 'full'}).json()
    except requests.RequestException as e:
        raise LookupError('Error getting trakt data for id %s: %s' % (trakt_id, e))


class ApiTrakt(object):

    @staticmethod
    @with_session
    def lookup_series(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None,
                      tvdb_id=None, tvrage_id=None, session=None, only_cached=None):
        series = None
        trakt_id = trakt_id or trakt_slug
        if not trakt_id:
            # Try finding trakt_id based on other ids
            ids = {
                'title': title,
                'tmdb': tmdb_id,
                'imdb': imdb_id
            }
            if style == 'show':
                ids['tvdb'] = tvdb_id
                ids['tvrage'] = tvrage_id
            def id_str():
                return '<name=%s, trakt_id=%s>' % (title, trakt_id)
            if ids:
                series = get_cached(title=title, imdb_id=imdb_id, tmdb_id=tmdb_id, tvdb_id=tvdb_id, tvrage_id=tvrage_id)
            if not series:
                if not series:
                    found = session.query(TraktSearchResult).filter(func.lower(TraktSearchResult.search) ==
                                                                    title.lower()).first()
                    if found and found.series:
                        series = get_cached(trakt_id=found.trakt_id)
            if not series:
                if only_cached:
                    raise LookupError('Series %s not found from cache' % id_str())
                log.debug('Series %s not found in cache, looking up from trakt.' % id_str())
                if ids:
                    results = get_trakt(title=title, imdb_id=imdb_id, tmdb_id=tmdb_id, tvdb_id=tvdb_id, tvrage_id=tvrage_id, style=style)
                    series = TraktShow()
                    series.update(results)
                    session.add(series)


            if not series:
                raise LookupError('No results found from traktv for %s' % id_str())

            # Make sure relations are loaded before returning
            #series.episodes
            #series.genre
            #series.actors
            return series

    @staticmethod
    @with_session
    def lookup_episode(title=None, seasonnum=None, episodenum=None, trakt_id=None, session=None, only_cached=False):
        series = get_cached(style='show', title=title, trakt_id=trakt_id, session=session)
        if not series:
            raise LookupError('Could not identify series')
        ep_description = '%s.S%sE%s' % (series.title, seasonnum, episodenum)
        episode = session.query(TraktEpisode).filter(TraktEpisode.id == series.trakt_id).\
            filter(TraktEpisode.season == seasonnum).filter(TraktEpisode.number == episodenum).first()
        url = episode_summary + api_key + '%s/%s/%s' % (series.tvdb_id, seasonnum, episodenum)
        if not episode:
            if only_cached:
                raise LookupError('Episode %s not found in cache' % ep_description)

            log.debug('Episode %s not found in cache, looking up from trakt.' % ep_description)
            try:
                response = requests.get(url)
            except requests.RequestException:
                raise LookupError('Error Retrieving Trakt url: %s' % url)
            try:
                data = response.json()
            except ValueError:
                raise LookupError('Error parsing Trakt episode json for %s' % title)
            if not data:
                raise LookupError('No data in response from trakt %s' % url)
            if 'error' in data:
                raise LookupError('Error looking up %s: %s' % (ep_description, data['error']))
            ep_data = data['episode']
            if not ep_data:
                raise LookupError('No episode data %s' % url)
            episode = session.query(TraktEpisode).filter(TraktEpisode.tvdb_id == ep_data['tvdb_id']).first()
            if not episode:
                # Update result into format TraktEpisode expects (?)
                ep_data['episode_name'] = ep_data.pop('title')
                ep_data.update(ep_data['images'])
                del ep_data['images']

                episode = TraktEpisode(ep_data)
                series.episodes.append(episode)
                session.merge(episode)

        return episode


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTrakt, 'api_trakt', api_ver=2)
