from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime, timedelta

from sqlalchemy import Table, Column, Integer, Float, Unicode, Boolean, DateTime, func, or_
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name
from flexget.utils import requests
from flexget.utils.database import text_date_synonym, year_property, with_session

log = logging.getLogger('api_tmdb')
Base = db_schema.versioned_base('api_tmdb', 1)

# This is a FlexGet API key
API_KEY = 'bdfc018dbdb7c243dc7cb1454ff74b95'
BASE_URL = 'https://api.themoviedb.org/3/'

_tmdb_config = None


def get_tmdb_config():
    """Gets and caches tmdb config on first call."""
    global _tmdb_config
    if not _tmdb_config:
        _tmdb_config = tmdb_request('configuration')
    return _tmdb_config


def tmdb_request(endpoint, **params):
    params.setdefault('api_key', API_KEY)
    full_url = BASE_URL + endpoint
    return requests.get(full_url, params=params).json()


@db_schema.upgrade('api_tmdb')
def upgrade(ver, session):
    if ver is None or ver <= 1:
        raise db_schema.UpgradeImpossible
    return ver


# association tables
genres_table = Table('tmdb_movie_genres', Base.metadata,
    Column('movie_id', Integer, ForeignKey('tmdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('tmdb_genres.id')))
Base.register_table(genres_table)


class TMDBMovie(Base):
    __tablename__ = 'tmdb_movies'

    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    imdb_id = Column(Unicode)
    url = Column(Unicode)
    name = Column(Unicode)
    original_name = Column(Unicode)
    alternative_name = Column(Unicode)
    _released = Column('released', DateTime)
    released = text_date_synonym('_released')
    year = year_property('released')
    certification = Column(Unicode)
    runtime = Column(Integer)
    language = Column(Unicode)
    overview = Column(Unicode)
    tagline = Column(Unicode)
    rating = Column(Float)
    votes = Column(Integer)
    popularity = Column(Integer)
    adult = Column(Boolean)
    budget = Column(Integer)
    revenue = Column(Integer)
    homepage = Column(Unicode)
    posters = relation('TMDBPoster', backref='movie', cascade='all, delete, delete-orphan')
    _genres = relation('TMDBGenre', secondary=genres_table, backref='movies')
    genres = association_proxy('_genres', 'name')
    updated = Column(DateTime, default=datetime.now, nullable=False)

    def __init__(self, id):
        """
        Looks up movie on tmdb and creates a new database model for it.
        These instances should only be added to a session via `session.merge`.
        """
        self.id = id
        try:
            movie = tmdb_request('movie/{}'.format(self.id), append_to_response='alternative_titles,images')
        except requests.RequestException as e:
            raise LookupError('Error updating data from tmdb: %s' % e)
        self.imdb_id = movie['imdb_id']
        self.name = movie['title']
        self.original_name = movie['original_title']
        self.released = movie['release_date']
        self.runtime = movie['runtime']
        self.language = movie['original_language']
        self.overview = movie['overview']
        self.tagline = movie['tagline']
        self.rating = movie['vote_average']
        self.votes = movie['vote_count']
        self.popularity = movie['popularity']
        self.adult = movie['adult']
        self.budget = movie['budget']
        self.revenue = movie['revenue']
        self.homepage = movie['homepage']
        self.alternative_name = None
        try:
            self.alternative_name = movie['alternative_titles']['titles'][0]['title']
        except (KeyError, IndexError):
            pass  # No alternate titles
        self._genres = [TMDBGenre(**g) for g in movie['genres']]
        # Just grab the top 5 posters
        self.posters = [TMDBPoster(**p) for p in movie['images']['posters'][:5]]
        self.updated = datetime.now()


class TMDBGenre(Base):

    __tablename__ = 'tmdb_genres'

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(Unicode, nullable=False)


class TMDBPoster(Base):

    __tablename__ = 'tmdb_posters'

    id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('tmdb_movies.id'))
    file_path = Column(Unicode)
    width = Column(Integer)
    height = Column(Integer)
    aspect_ratio = Column(Float)
    vote_average = Column(Float)
    vote_count = Column(Integer)
    iso_639_1 = Column(Unicode)

    @property
    def url(self):
        return get_tmdb_config()['images']['base_url'] + 'original' + self.file_path


class TMDBSearchResult(Base):

    __tablename__ = 'tmdb_search_results'

    search = Column(Unicode, primary_key=True)
    movie_id = Column(Integer, ForeignKey('tmdb_movies.id'), nullable=True)
    movie = relation(TMDBMovie)

    def __init__(self, search, movie_id=None, movie=None):
        self.search = search.lower()
        if movie_id:
            self.movie_id = movie_id
        if movie:
            self.movie = movie


class ApiTmdb(object):
    """Does lookups to TMDb and provides movie information. Caches lookups."""

    @staticmethod
    @with_session
    def lookup(title=None, year=None, tmdb_id=None, imdb_id=None, smart_match=None, only_cached=False, session=None):
        """
        Do a lookup from TMDb for the movie matching the passed arguments.

        Any combination of criteria can be passed, the most specific criteria specified will be used.

        :param int tmdb_id: tmdb_id of desired movie
        :param unicode imdb_id: imdb_id of desired movie
        :param unicode title: title of desired movie
        :param int year: release year of desired movie
        :param unicode smart_match: attempt to clean and parse title and year from a string
        :param bool only_cached: if this is specified, an online lookup will not occur if the movie is not in the cache
        session: optionally specify a session to use, if specified, returned Movie will be live in that session
        :param session: sqlalchemy Session in which to do cache lookups/storage. commit may be called on a passed in
            session. If not supplied, a session will be created automatically.

        :return: The :class:`TMDBMovie` object populated with data from tmdb

        :raises: :class:`LookupError` if a match cannot be found or there are other problems with the lookup
        """
        if smart_match and not (title or tmdb_id or imdb_id):
            # If smart_match was specified, parse it into a title and year
            title_parser = get_plugin_by_name('parsing').instance.parse_movie(smart_match)
            title = title_parser.name
            year = title_parser.year
        if not (title or tmdb_id or imdb_id):
            raise LookupError('No criteria specified for TMDb lookup')
        id_str = '<title={}, year={}, tmdb_id={}, imdb_id={}>'.format(title, year, tmdb_id, imdb_id)

        log.debug('Looking up TMDb information for %s', id_str)
        movie = None
        if imdb_id or tmdb_id:
            ors = []
            if tmdb_id:
                ors.append(TMDBMovie.id == tmdb_id)
            if imdb_id:
                ors.append(TMDBMovie.imdb_id == imdb_id)
            movie = session.query(TMDBMovie).filter(or_(*ors)).first()
        elif title:
            movie_filter = session.query(TMDBMovie).filter(func.lower(TMDBMovie.name) == title.lower())
            if year:
                movie_filter = movie_filter.filter(TMDBMovie.year == year)
            movie = movie_filter.first()
            if not movie:
                search_string = title + ' ({})'.format(year) if year else ''
                found = session.query(TMDBSearchResult). \
                    filter(TMDBSearchResult.search == search_string.lower()).first()
                if found and found.movie:
                    movie = found.movie
        if movie:
            # Movie found in cache, check if cache has expired.
            refresh_time = timedelta(days=2)
            if movie.released:
                if movie.released > datetime.now() - timedelta(days=7):
                    # Movie is less than a week old, expire after 1 day
                    refresh_time = timedelta(days=1)
                else:
                    age_in_years = (datetime.now() - movie.released).days / 365
                    refresh_time += timedelta(days=age_in_years * 5)
            if movie.updated < datetime.now() - refresh_time and not only_cached:
                log.debug('Cache has expired for %s, attempting to refresh from TMDb.', movie.name)
                try:
                    updated_movie = TMDBMovie(id=movie.id)
                except LookupError:
                    log.error('Error refreshing movie details from TMDb, cached info being used.')
                else:
                    movie = session.merge(updated_movie)
            else:
                log.debug('Movie %s information restored from cache.', movie.name)
        else:
            if only_cached:
                raise LookupError('Movie %s not found from cache' % id_str)
            # There was no movie found in the cache, do a lookup from tmdb
            log.verbose('Searching from TMDb %s', id_str)
            if imdb_id and not tmdb_id:
                try:
                    result = tmdb_request('find/{}'.format(imdb_id), external_source='imdb_id')
                except requests.RequestException as e:
                    raise LookupError('Error searching imdb id on tmdb: {}'.format(e))
                if result['movie_results']:
                    tmdb_id = result['movie_results'][0]['id']
            if not tmdb_id:
                search_string = title + ' ({})'.format(year) if year else ''
                searchparams = {'query': title}
                if year:
                    searchparams['year'] = year
                try:
                    results = tmdb_request('search/movie', **searchparams)
                except requests.RequestException as e:
                    raise LookupError('Error searching for tmdb item {}: {}'.format(search_string, e))
                if not results['results']:
                    raise LookupError('No resuts for {} from tmdb'.format(search_string))
                tmdb_id = results['results'][0]['id']
                session.add(TMDBSearchResult(search=search_string, movie_id=tmdb_id))
            if tmdb_id:
                movie = TMDBMovie(id=tmdb_id)
                movie = session.merge(movie)
            else:
                raise LookupError('Unable to find movie on tmdb: {}'.format(id_str))

        return movie


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTmdb, 'api_tmdb', api_ver=2)
