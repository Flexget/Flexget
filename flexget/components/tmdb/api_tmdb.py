from datetime import datetime, timedelta

from dateutil.parser import parse as dateutil_parse
from loguru import logger
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Table,
    Unicode,
    func,
    or_,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils import requests
from flexget.utils.database import json_synonym, with_session, year_property

logger = logger.bind(name='api_tmdb')
Base = db_schema.versioned_base('api_tmdb', 6)

# This is a FlexGet API key
API_KEY = 'bdfc018dbdb7c243dc7cb1454ff74b95'
BASE_URL = 'https://api.themoviedb.org/3/'

_tmdb_config = None


class TMDBConfig(Base):
    __tablename__ = 'tmdb_configuration'

    id = Column(Integer, primary_key=True)
    _configuration = Column('configuration', Unicode)
    configuration = json_synonym('_configuration')
    updated = Column(DateTime, default=datetime.now, nullable=False)

    def __init__(self):
        try:
            configuration = tmdb_request('configuration')
        except requests.RequestException as e:
            raise LookupError('Error updating data from tmdb: %s' % e)
        self.configuration = configuration

    @property
    def expired(self):
        if self.updated < datetime.now() - timedelta(days=5):
            return True
        return False


def get_tmdb_config():
    """Loads TMDB config and caches it in DB and memory"""
    global _tmdb_config
    if _tmdb_config is None:
        logger.debug('no tmdb configuration in memory, checking cache')
        with Session() as session:
            config = session.query(TMDBConfig).first()
            if not config or config.expired:
                logger.debug('no config cached or config expired, refreshing')
                config = session.merge(TMDBConfig())
            _tmdb_config = config.configuration
    return _tmdb_config


def tmdb_request(endpoint, **params):
    params.setdefault('api_key', API_KEY)
    full_url = BASE_URL + endpoint
    return requests.get(full_url, params=params).json()


@db_schema.upgrade('api_tmdb')
def upgrade(ver, session):
    if ver is None or ver <= 5:
        raise db_schema.UpgradeImpossible
    return ver


# association tables
genres_table = Table(
    'tmdb_movie_genres',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('tmdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('tmdb_genres.id')),
)
Base.register_table(genres_table)


class TMDBMovie(Base):
    __tablename__ = 'tmdb_movies'

    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    imdb_id = Column(Unicode)
    url = Column(Unicode)
    name = Column(Unicode)
    original_name = Column(Unicode)
    alternative_name = Column(Unicode)
    released = Column(Date)
    year = year_property('released')
    runtime = Column(Integer)
    language = Column(Unicode)
    overview = Column(Unicode)
    tagline = Column(Unicode)
    rating = Column(Float)
    votes = Column(Integer)
    popularity = Column(Float)
    adult = Column(Boolean)
    budget = Column(Integer)
    revenue = Column(Integer)
    homepage = Column(Unicode)
    lookup_language = Column(String)
    _posters = relation('TMDBPoster', backref='movie', cascade='all, delete, delete-orphan')
    _backdrops = relation('TMDBBackdrop', backref='movie', cascade='all, delete, delete-orphan')
    _genres = relation('TMDBGenre', secondary=genres_table, backref='movies')
    genres = association_proxy('_genres', 'name')
    updated = Column(DateTime, default=datetime.now, nullable=False)

    def __init__(self, id, language):
        """
        Looks up movie on tmdb and creates a new database model for it.
        These instances should only be added to a session via `session.merge`.
        """
        self.id = id
        try:
            movie = tmdb_request(
                f'movie/{self.id}',
                append_to_response='alternative_titles',
                language=language,
            )
        except requests.RequestException as e:
            raise LookupError('Error updating data from tmdb: %s' % e)
        self.imdb_id = movie['imdb_id']
        self.name = movie['title']
        self.original_name = movie['original_title']
        if movie.get('release_date'):
            self.released = dateutil_parse(movie['release_date']).date()
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
        self.lookup_language = language
        try:
            self.alternative_name = movie['alternative_titles']['titles'][0]['title']
        except (KeyError, IndexError):
            # No alternate titles
            self.alternative_name = None
        self._genres = [TMDBGenre(**g) for g in movie['genres']]
        self.updated = datetime.now()

    def get_images(self):
        logger.debug('images for movie {} not found in DB, fetching from TMDB', self.name)
        try:
            images = tmdb_request(f'movie/{self.id}/images')
        except requests.RequestException as e:
            raise LookupError('Error updating data from tmdb: %s' % e)

        self._posters = [TMDBPoster(movie_id=self.id, **p) for p in images['posters']]
        self._backdrops = [TMDBBackdrop(movie_id=self.id, **b) for b in images['backdrops']]

    @property
    def posters(self):
        if not self._posters:
            self.get_images()
        return self._posters

    @property
    def backdrops(self):
        if not self._backdrops:
            self.get_images()
        return self._backdrops

    def to_dict(self):
        return {
            'id': self.id,
            'imdb_id': self.imdb_id,
            'name': self.name,
            'original_name': self.original_name,
            'alternative_name': self.alternative_name,
            'year': self.year,
            'runtime': self.runtime,
            'language': self.language,
            'overview': self.overview,
            'tagline': self.tagline,
            'rating': self.rating,
            'votes': self.votes,
            'popularity': self.popularity,
            'adult': self.adult,
            'budget': self.budget,
            'revenue': self.revenue,
            'homepage': self.homepage,
            'genres': list(self.genres),
            'updated': self.updated,
            'lookup_language': self.lookup_language,
        }


class TMDBGenre(Base):
    __tablename__ = 'tmdb_genres'

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(Unicode, nullable=False)


class TMDBImage(Base):
    __tablename__ = 'tmdb_images'

    id = Column(Integer, primary_key=True, autoincrement=True)
    movie_id = Column(Integer, ForeignKey('tmdb_movies.id'))
    file_path = Column(Unicode)
    width = Column(Integer)
    height = Column(Integer)
    aspect_ratio = Column(Float)
    vote_average = Column(Float)
    vote_count = Column(Integer)
    iso_639_1 = Column(Unicode)
    type = Column(Unicode)
    __mapper_args__ = {'polymorphic_on': type}

    def url(self, size):
        return get_tmdb_config()['images']['base_url'] + size + self.file_path

    def to_dict(self):
        return {
            'id': self.id,
            'urls': {
                size: self.url(size) for size in get_tmdb_config()['images'][self.type + '_sizes']
            },
            'movie_id': self.movie_id,
            'file_path': self.file_path,
            'width': self.width,
            'height': self.height,
            'aspect_ratio': self.aspect_ratio,
            'vote_average': self.vote_average,
            'vote_count': self.vote_count,
            'language_code': self.iso_639_1,
        }


class TMDBPoster(TMDBImage):
    __mapper_args__ = {'polymorphic_identity': 'poster'}


class TMDBBackdrop(TMDBImage):
    __mapper_args__ = {'polymorphic_identity': 'backdrop'}


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


class ApiTmdb:
    """Does lookups to TMDb and provides movie information. Caches lookups."""

    @staticmethod
    @with_session
    def lookup(
        title=None,
        year=None,
        tmdb_id=None,
        imdb_id=None,
        smart_match=None,
        only_cached=False,
        session=None,
        language='en',
    ):
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
        :param language: Specify title lookup language
        :param session: sqlalchemy Session in which to do cache lookups/storage. commit may be called on a passed in
            session. If not supplied, a session will be created automatically.

        :return: The :class:`TMDBMovie` object populated with data from tmdb

        :raises: :class:`LookupError` if a match cannot be found or there are other problems with the lookup
        """

        # Populate tmdb config
        get_tmdb_config()

        if smart_match and not (title or tmdb_id or imdb_id):
            # If smart_match was specified, parse it into a title and year
            title_parser = plugin.get('parsing', 'api_tmdb').parse_movie(smart_match)
            title = title_parser.name
            year = title_parser.year
        if not (title or tmdb_id or imdb_id):
            raise LookupError('No criteria specified for TMDb lookup')
        id_str = '<title={}, year={}, tmdb_id={}, imdb_id={}>'.format(
            title, year, tmdb_id, imdb_id
        )

        logger.debug('Looking up TMDb information for {}', id_str)
        movie = None
        if imdb_id or tmdb_id:
            ors = []
            if tmdb_id:
                ors.append(TMDBMovie.id == tmdb_id)
            if imdb_id:
                ors.append(TMDBMovie.imdb_id == imdb_id)
            movie = session.query(TMDBMovie).filter(or_(*ors)).first()
        elif title:
            movie_filter = session.query(TMDBMovie).filter(
                func.lower(TMDBMovie.name) == title.lower()
            )
            if year:
                movie_filter = movie_filter.filter(TMDBMovie.year == year)
            movie = movie_filter.first()
            if not movie:
                search_string = title + f' ({year})' if year else title
                found = (
                    session.query(TMDBSearchResult)
                    .filter(TMDBSearchResult.search == search_string.lower())
                    .first()
                )
                if found and found.movie:
                    movie = found.movie
        if movie:
            # Movie found in cache, check if cache has expired.
            refresh_time = timedelta(days=2)
            if movie.released:
                if movie.released > datetime.now().date() - timedelta(days=7):
                    # Movie is less than a week old, expire after 1 day
                    refresh_time = timedelta(days=1)
                else:
                    age_in_years = (datetime.now().date() - movie.released).days / 365
                    refresh_time += timedelta(days=age_in_years * 5)
            if movie.updated < datetime.now() - refresh_time and not only_cached:
                logger.debug(
                    'Cache has expired for {}, attempting to refresh from TMDb.', movie.name
                )
                try:
                    updated_movie = TMDBMovie(id=movie.id, language=language)
                except LookupError:
                    logger.error(
                        'Error refreshing movie details from TMDb, cached info being used.'
                    )
                else:
                    movie = session.merge(updated_movie)
            else:
                logger.debug('Movie {} information restored from cache.', movie.name)
        else:
            if only_cached:
                raise LookupError('Movie %s not found from cache' % id_str)
            # There was no movie found in the cache, do a lookup from tmdb
            logger.verbose('Searching from TMDb {}', id_str)
            if imdb_id and not tmdb_id:
                try:
                    result = tmdb_request(f'find/{imdb_id}', external_source='imdb_id')
                except requests.RequestException as e:
                    raise LookupError(f'Error searching imdb id on tmdb: {e}')
                if result['movie_results']:
                    tmdb_id = result['movie_results'][0]['id']
            if not tmdb_id:
                search_string = title + f' ({year})' if year else title
                search_params = {'query': title, 'language': language}
                if year:
                    search_params['year'] = year
                try:
                    results = tmdb_request('search/movie', **search_params)
                except requests.RequestException as e:
                    raise LookupError(f'Error searching for tmdb item {search_string}: {e}')
                if not results['results']:
                    raise LookupError(f'No results for {search_string} from tmdb')
                tmdb_id = results['results'][0]['id']
                session.add(TMDBSearchResult(search=search_string, movie_id=tmdb_id))
            if tmdb_id:
                movie = TMDBMovie(id=tmdb_id, language=language)
                movie = session.merge(movie)
            else:
                raise LookupError(f'Unable to find movie on tmdb: {id_str}')

        return movie


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTmdb, 'api_tmdb', api_ver=2, interfaces=[])
