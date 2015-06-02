from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
import logging
import os
import posixpath
import socket
import sys
from urllib2 import URLError

from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.utils import requests
from flexget.utils.database import text_date_synonym, year_property, with_session
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema

try:
    import tmdb3
except ImportError:
    raise plugin.DependencyError(issued_by='api_tmdb', missing='tmdb3',
                                 message='TMDB requires https://github.com/wagnerrp/pytmdb3')

log = logging.getLogger('api_tmdb')
Base = db_schema.versioned_base('api_tmdb', 0)

# This is a FlexGet API key
tmdb3.tmdb_api.set_key('bdfc018dbdb7c243dc7cb1454ff74b95')
tmdb3.locales.set_locale("en", "us", True)
# There is a bug in tmdb3 library, where it uses the system encoding for query parameters, tmdb expects utf-8 #2392
tmdb3.locales.syslocale.encoding = 'utf-8'
tmdb3.set_cache('null')


@db_schema.upgrade('api_tmdb')
def upgrade(ver, session):
    if ver is None:
        log.info('Adding columns to tmdb cache table, marking current cache as expired.')
        table_add_column('tmdb_movies', 'runtime', Integer, session)
        table_add_column('tmdb_movies', 'tagline', Unicode, session)
        table_add_column('tmdb_movies', 'budget', Integer, session)
        table_add_column('tmdb_movies', 'revenue', Integer, session)
        table_add_column('tmdb_movies', 'homepage', String, session)
        table_add_column('tmdb_movies', 'trailer', String, session)
        # Mark all cached movies as expired, so new fields get populated next lookup
        movie_table = table_schema('tmdb_movies', session)
        session.execute(movie_table.update(values={'updated': datetime(1970, 1, 1)}))
        ver = 0
    return ver


# association tables
genres_table = Table('tmdb_movie_genres', Base.metadata,
    Column('movie_id', Integer, ForeignKey('tmdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('tmdb_genres.id')))


class TMDBContainer(object):
    """Base class for TMDb objects"""

    def __init__(self, init_object=None):
        if isinstance(init_object, dict):
            self.update_from_dict(init_object)
        elif init_object:
            self.update_from_object(init_object)

    def update_from_dict(self, update_dict):
        """Populates any simple (string or number) attributes from a dict"""
        for col in self.__table__.columns:
            if isinstance(update_dict.get(col.name), (basestring, int, float)):
                setattr(self, col.name, update_dict[col.name])

    def update_from_object(self, update_object):
        """Populates any simple (string or number) attributes from object attributes"""
        for col in self.__table__.columns:
            if (hasattr(update_object, col.name) and
                    isinstance(getattr(update_object, col.name), (basestring, int, float))):
                setattr(self, col.name, getattr(update_object, col.name))


class TMDBMovie(TMDBContainer, Base):
    __tablename__ = 'tmdb_movies'

    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    updated = Column(DateTime, default=datetime.now, nullable=False)
    popularity = Column(Integer)
    translated = Column(Boolean)
    adult = Column(Boolean)
    language = Column(String)
    original_name = Column(Unicode)
    name = Column(Unicode)
    alternative_name = Column(Unicode)
    movie_type = Column(String)
    imdb_id = Column(String)
    url = Column(String)
    votes = Column(Integer)
    rating = Column(Float)
    certification = Column(String)
    overview = Column(Unicode)
    runtime = Column(Integer)
    tagline = Column(Unicode)
    budget = Column(Integer)
    revenue = Column(Integer)
    homepage = Column(String)
    trailer = Column(String)
    _released = Column('released', DateTime)
    released = text_date_synonym('_released')
    year = year_property('released')
    posters = relation('TMDBPoster', backref='movie', cascade='all, delete, delete-orphan')
    genres = relation('TMDBGenre', secondary=genres_table, backref='movies')

    def update_from_object(self, update_object):
        try:
            TMDBContainer.update_from_object(self, update_object)
            self.translated = len(update_object.translations) > 0
            if len(update_object.languages) > 0:
                self.language = update_object.languages[0].code # .code or .name ?
            self.original_name = update_object.originaltitle
            self.name = update_object.title
            try:
                if len(update_object.alternate_titles) > 0:
                    # maybe we could choose alternate title from movie country only
                    self.alternative_name = update_object.alternate_titles[0].title
            except UnicodeEncodeError:
                # Bug in tmdb3 library, see #2437. Just don't set alternate_name when it fails
                pass
            self.imdb_id = update_object.imdb
            self.url = update_object.homepage
            self.rating = update_object.userrating
            if len(update_object.youtube_trailers) > 0:
                self.trailer = update_object.youtube_trailers[0].source # unicode: ooNSm6Uug3g
            elif len(update_object.apple_trailers) > 0:
                self.trailer = update_object.apple_trailers[0].source
            self.released = update_object.releasedate
        except tmdb3.TMDBError as e:
            raise LookupError('Error updating data from tmdb: %s' % e)


class TMDBGenre(TMDBContainer, Base):

    __tablename__ = 'tmdb_genres'

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String, nullable=False)


class TMDBPoster(TMDBContainer, Base):

    __tablename__ = 'tmdb_posters'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('tmdb_movies.id'))
    size = Column(String)
    url = Column(String)
    file = Column(Unicode)

    def get_file(self, only_cached=False):
        """Makes sure the poster is downloaded to the local cache (in userstatic folder) and
        returns the path split into a list of directory and file components"""
        from flexget.manager import manager
        base_dir = os.path.join(manager.config_base, 'userstatic')
        if self.file and os.path.isfile(os.path.join(base_dir, self.file)):
            return self.file.split(os.sep)
        elif only_cached:
            return
        # If we don't already have a local copy, download one.
        log.debug('Downloading poster %s' % self.url)
        dirname = os.path.join('tmdb', 'posters', str(self.movie_id))
        # Create folders if they don't exist
        fullpath = os.path.join(base_dir, dirname)
        if not os.path.isdir(fullpath):
            os.makedirs(fullpath)
        filename = os.path.join(dirname, posixpath.basename(self.url))
        thefile = file(os.path.join(base_dir, filename), 'wb')
        thefile.write(requests.get(self.url).content)
        self.file = filename
        # If we are detached from a session, update the db
        if not Session.object_session(self):
            session = Session()
            try:
                poster = session.query(TMDBPoster).filter(TMDBPoster.db_id == self.db_id).first()
                if poster:
                    poster.file = filename
            finally:
                session.close()
        return filename.split(os.sep)


class TMDBSearchResult(Base):

    __tablename__ = 'tmdb_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, nullable=False)
    movie_id = Column(Integer, ForeignKey('tmdb_movies.id'), nullable=True)
    movie = relation(TMDBMovie, backref='search_strings')


class ApiTmdb(object):
    """Does lookups to TMDb and provides movie information. Caches lookups."""

    @staticmethod
    @with_session(expire_on_commit=False)
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

        if not (tmdb_id or imdb_id or title) and smart_match:
            # If smart_match was specified, and we don't have more specific criteria, parse it into a title and year
            title_parser = get_plugin_by_name('parsing').instance.parse_movie(smart_match)
            title = title_parser.name
            year = title_parser.year

        if title:
            search_string = title.lower()
            if year:
                search_string = '%s (%s)' % (search_string, year)
        elif not (tmdb_id or imdb_id):
            raise LookupError('No criteria specified for TMDb lookup')
        log.debug('Looking up TMDb information for %r' % {'title': title, 'tmdb_id': tmdb_id, 'imdb_id': imdb_id})

        movie = None

        def id_str():
            return '<title=%s,tmdb_id=%s,imdb_id=%s>' % (title, tmdb_id, imdb_id)
        if tmdb_id:
            movie = session.query(TMDBMovie).filter(TMDBMovie.id == tmdb_id).first()
        if not movie and imdb_id:
            movie = session.query(TMDBMovie).filter(TMDBMovie.imdb_id == imdb_id).first()
        if not movie and title:
            movie_filter = session.query(TMDBMovie).filter(func.lower(TMDBMovie.name) == title.lower())
            if year:
                movie_filter = movie_filter.filter(TMDBMovie.year == year)
            movie = movie_filter.first()
            if not movie:
                found = session.query(TMDBSearchResult). \
                    filter(func.lower(TMDBSearchResult.search) == search_string).first()
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
                log.debug('Cache has expired for %s, attempting to refresh from TMDb.' % id_str())
                try:
                    ApiTmdb.get_movie_details(movie, session)
                except URLError:
                    log.error('Error refreshing movie details from TMDb, cached info being used.')
            else:
                log.debug('Movie %s information restored from cache.' % id_str())
        else:
            if only_cached:
                raise LookupError('Movie %s not found from cache' % id_str())
            # There was no movie found in the cache, do a lookup from tmdb
            log.verbose('Searching from TMDb %s' % id_str())
            try:
                if imdb_id and not tmdb_id:
                    result = tmdb3.Movie.fromIMDB(imdb_id)
                    if result:
                        movie = session.query(TMDBMovie).filter(TMDBMovie.id == result.id).first()
                        if movie:
                            # Movie was in database, but did not have the imdb_id stored, force an update
                            ApiTmdb.get_movie_details(movie, session, result)
                        else:
                            tmdb_id = result.id
                if tmdb_id:
                    movie = TMDBMovie()
                    movie.id = tmdb_id
                    ApiTmdb.get_movie_details(movie, session)
                    if movie.name:
                        session.merge(movie)
                    else:
                        movie = None
                elif title:
                    try:
                        result = _first_result(tmdb3.tmdb_api.searchMovie(title.lower(), adult=True, year=year))
                    except socket.timeout:
                        raise LookupError('Timeout contacting TMDb')
                    if not result and year:
                        result = _first_result(tmdb3.tmdb_api.searchMovie(title.lower(), adult=True))
                    if result:
                        movie = session.query(TMDBMovie).filter(TMDBMovie.id == result.id).first()
                        if not movie:
                            movie = TMDBMovie(result)
                            ApiTmdb.get_movie_details(movie, session, result)
                            session.merge(movie)
                        if title.lower() != movie.name.lower():
                            session.merge(TMDBSearchResult(search=search_string, movie=movie))
            except tmdb3.TMDBError as e:
                raise LookupError('Error looking up movie from TMDb (%s)' % e)
            if movie:
                log.verbose("Movie found from TMDb: %s (%s)" % (movie.name, movie.year))

        if not movie:
            raise LookupError('No results found from tmdb for %s' % id_str())
        else:
            session.commit()
            return movie

    @staticmethod
    def get_movie_details(movie, session, result=None):
        """Populate details for this :movie: from TMDb"""

        if not result and not movie.id:
            raise LookupError('Cannot get tmdb details without tmdb id')
        if not result:
            try:
                result = tmdb3.Movie(movie.id)
            except tmdb3.TMDBError:
                raise LookupError('No results for tmdb_id: %s (%s)' % (movie.id, sys.exc_info()[1]))
            try:
                movie.update_from_object(result)
            except tmdb3.TMDBRequestInvalid as e:
                log.debug('Error updating tmdb info: %s' % e)
                raise LookupError('Error getting tmdb info')
        posters = result.posters
        if posters:
            # Add any posters we don't already have
            # TODO: There are quite a few posters per movie, do we need to cache them all?
            poster_urls = [p.url for p in movie.posters]
            for item in posters:
                for size in item.sizes():
                    url = item.geturl(size)
                    if url not in poster_urls:
                        poster_data = {"movie_id": movie.id, "size": size, "url": url, "file": item.filename}
                        movie.posters.append(TMDBPoster(poster_data))
        genres = result.genres
        if genres:
            for genre in genres:
                if not genre.id:
                    continue
                db_genre = session.query(TMDBGenre).filter(TMDBGenre.id == genre.id).first()
                if not db_genre:
                    db_genre = TMDBGenre(genre)
                if db_genre not in movie.genres:
                    movie.genres.append(db_genre)
        movie.updated = datetime.now()


def _first_result(results):
    if results and len(results) >= 1:
        return results[0]


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTmdb, 'api_tmdb', api_ver=2)
