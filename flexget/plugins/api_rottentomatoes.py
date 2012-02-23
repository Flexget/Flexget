from datetime import datetime, timedelta
import logging
from urllib2 import URLError
from sqlalchemy import Table, Column, Integer, String, DateTime, func
from sqlalchemy.schema import ForeignKey, Index
from sqlalchemy.orm import relation
from flexget import schema
from flexget.utils import json
from flexget.utils.titles import MovieParser
from flexget.utils.tools import urlopener
from flexget.utils.database import text_date_synonym, with_session

log = logging.getLogger('api_rottentomatoes')
Base = schema.versioned_base('api_rottentomatoes', 0)

# This is developer Atlanta800's API key
API_KEY = 'rh8chjzp8vu6gnpwj88736uv'
API_VER = 'v1.0'
SERVER = 'http://api.rottentomatoes.com/api/public'


# association tables
genres_table = Table('rottentomatoes_movie_genres', Base.metadata,
    Column('movie_id', Integer, ForeignKey('rottentomatoes_movies.id')),
    Column('genre_id', Integer, ForeignKey('rottentomatoes_genres.id')),
    Index('ix_rottentomatoes_movie_genres', 'movie_id', 'genre_id'))

actors_table = Table('rottentomatoes_movie_actors', Base.metadata,
    Column('movie_id', Integer, ForeignKey('rottentomatoes_movies.id')),
    Column('actor_id', Integer, ForeignKey('rottentomatoes_actors.id')),
    Index('ix_rottentomatoes_movie_actors', 'movie_id', 'actor_id'))

directors_table = Table('rottentomatoes_movie_directors', Base.metadata,
    Column('movie_id', Integer, ForeignKey('rottentomatoes_movies.id')),
    Column('director_id', Integer, ForeignKey('rottentomatoes_directors.id')),
    Index('ix_rottentomatoes_movie_directors', 'movie_id', 'director_id'))


class RottenTomatoesContainer(object):
    """Base class for RottenTomatoes objects"""

    def __init__(self, init_dict=None):
        if isinstance(init_dict, dict):
            self.update_from_dict(init_dict)

    def update_from_dict(self, update_dict):
        """Populates any simple (string or number) attributes from a dict"""
        for col in self.__table__.columns:
            if isinstance(update_dict.get(col.name), (basestring, int, float)):
                setattr(self, col.name, update_dict[col.name])


class RottenTomatoesMovie(RottenTomatoesContainer, Base):

    __tablename__ = 'rottentomatoes_movies'

    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    title = Column(String)
    year = Column(Integer)
    genres = relation('RottenTomatoesGenre', secondary=genres_table, backref='movies')
    mpaa_rating = Column(String)
    runtime = Column(Integer)
    critics_consensus = Column(String)
    release_dates = relation('ReleaseDate', backref='movie', cascade='all, delete, delete-orphan')
    critics_rating = Column(String)
    critics_score = Column(Integer)
    audience_rating = Column(String)
    audience_score = Column(Integer)
    synopsis = Column(String)
    posters = relation('RottenTomatoesPoster', backref='movie', cascade='all, delete, delete-orphan')
    cast = relation('RottenTomatoesActor', secondary=actors_table, backref='movies')
    directors = relation('RottenTomatoesDirector', secondary=directors_table, backref='movies')
    studio = Column(String)
    alternate_ids = relation('RottenTomatoesAlternateId', backref='movie', cascade='all, delete, delete-orphan')
    links = relation('RottenTomatoesLink', backref='movie', cascade='all, delete, delete-orphan')

    # updated time, so we can grab new rating counts after 48 hours
    # set a default, so existing data gets updated with a rating
    updated = Column(DateTime)

    @property
    def expired(self):
        """
        :return: True if movie details are considered to be expired, ie. need of update
        """
        if self.updated is None:
            log.debug('updated is None: %s' % self)
            return True
        refresh_interval = 2
        if self.year:
            age = (datetime.now().year - self.year)
            refresh_interval += age * 5
            log.debug('movie `%s` age %i expires in %i days' % (self.title, age, refresh_interval))
        return self.updated < datetime.now() - timedelta(days=refresh_interval)

    def __repr__(self):
        return '<RottenTomatoesMovie(title=%s,audience_rating=%s,year=%s)>' % (self.title, self.audience_rating, self.year)


class RottenTomatoesGenre(Base):

    __tablename__ = 'rottentomatoes_genres'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name


class ReleaseDate(Base):

    __tablename__ = 'rottentomatoes_releasedates'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    date = text_date_synonym('_date')
    _date = Column('date', DateTime)

    def __init__(self, name, date):
        self.name = name
        self.date = date


class RottenTomatoesPoster(Base):

    __tablename__ = 'rottentomatoes_posters'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    url = Column(String)

    def __init__(self, name, url):
        self.name = name
        self.url = url


class RottenTomatoesActor(Base):

    __tablename__ = 'rottentomatoes_actors'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name


class RottenTomatoesDirector(Base):

    __tablename__ = 'rottentomatoes_directors'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name


class RottenTomatoesAlternateId(Base):

    __tablename__ = 'rottentomatoes_alternate_ids'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    id = Column(String)

    def __init__(self, name, id):
        self.name = name
        self.id = id


class RottenTomatoesLink(Base):

    __tablename__ = 'rottentomatoes_links'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    url = Column(String)

    def __init__(self, name, url):
        self.name = name
        self.url = url


class RottenTomatoesSearchResult(Base):

    __tablename__ = 'rottentomatoes_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(String, nullable=False)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'), nullable=True)
    movie = relation(RottenTomatoesMovie, backref='search_strings')

    def __repr__(self):
        return '<RottenTomatoesSearchResult(search=%s,movie_id=%s,movie=%s)>' % (self.search, self.movie_id, self.movie)


@with_session
def lookup_movie(title=None, year=None, rottentomatoes_id=None, imdb_id=None, smart_match=None, only_cached=False, session=None):
    """Do a lookup from Rotten Tomatoes for the movie matching the passed arguments.

    Any combination of criteria can be passed, the most specific criteria specified will be used.

    Returns:
        The Movie object populated with data from Rotten Tomatoes

    Raises:
        LookupError if a match cannot be found or there are other problems with the lookup

    Args:
        rottentomatoes_id: rottentomatoes_id of desired movie
        imdb_id: imdb_id of desired movie
        title: title of desired movie
        year: release year of desired movie
        smart_match: attempt to clean and parse title and year from a string
        only_cached: if this is specified, an online lookup will not occur if the movie is not in the cache
        session: optionally specify a session to use, if specified, returned Movie will be live in that session
    """

    if not (rottentomatoes_id or imdb_id or title) and smart_match:
        # If smart_match was specified, and we don't have more specific criteria, parse it into a title and year
        title_parser = MovieParser()
        title_parser.parse(smart_match)
        title = title_parser.name
        year = title_parser.year

    if title:
        search_string = title.lower()
        if year:
            search_string = '%s %s' % (search_string, year)
    elif not (rottentomatoes_id or imdb_id):
        raise LookupError('No criteria specified for rotten tomatoes lookup')
    log.debug('Looking up rotten tomatoes information for %r' % {'title': title, 'rottentomatoes_id': rottentomatoes_id, 'imdb_id': imdb_id})

    movie = None

    def id_str():
        return '<title=%s,rottentomatoes_id=%s,imdb_id=%s>' % (title, rottentomatoes_id, imdb_id)
    if rottentomatoes_id:
        movie = session.query(RottenTomatoesMovie).filter(RottenTomatoesMovie.id == rottentomatoes_id).first()
    if not movie and imdb_id:
        alt_id = session.query(RottenTomatoesAlternateId).filter(RottenTomatoesAlternateId.id == imdb_id).first()
        if alt_id:
            movie = session.query(RottenTomatoesMovie).filter(RottenTomatoesMovie.id == alt_id.movie_id).first()
    if not movie and title:
        movie_filter = session.query(RottenTomatoesMovie).filter(func.lower(RottenTomatoesMovie.title) == title.lower())
        if year:
            movie_filter = movie_filter.filter(RottenTomatoesMovie.year == year)
        movie = movie_filter.first()
        if not movie:
            found = session.query(RottenTomatoesSearchResult). \
                    filter(func.lower(RottenTomatoesSearchResult.search) == search_string).first()
            if found and found.movie:
                movie = found.movie
    if movie:
        # Movie found in cache, check if cache has expired.
        if movie.expired() and not only_cached:
            log.debug('Cache has expired for %s, attempting to refresh from Rotten Tomatoes.' % id_str())
            try:
                get_movie_details(movie, session)
            except URLError:
                log.error('Error refreshing movie details from Rotten Tomatoes, cached info being used.')
        else:
            log.debug('Movie %s information restored from cache.' % id_str())
    else:
        if only_cached:
            raise LookupError('Movie %s not found from cache' % id_str())
        # There was no movie found in the cache, do a lookup from Rotten Tomatoes
        log.debug('Movie %s not found in cache, looking up from rotten tomatoes.' % id_str())
        try:
            if imdb_id:
                result = movies_alias(imdb_id, 'imdb')
                if result:
                    movie = session.query(RottenTomatoesMovie).filter(RottenTomatoesMovie.id == result.get('id')).first()
                    if movie:
                        # Movie was in database, but did not have the imdb_id stored, force an update
                        get_movie_details(movie, session)
                    else:
                        movie = RottenTomatoesMovie()
                        get_movie_details(movie, session, result)
            elif rottentomatoes_id:
                movie = RottenTomatoesMovie()
                movie.id = rottentomatoes_id
                get_movie_details(movie, session)
                if movie.title:
                    session.merge(movie)
                else:
                    movie = None
            elif title:
                results = movies_search(search_string)
                if results:
                    results = results.get('movies')
                    if len(results) > 0 and year:
                        results = filter(lambda movie_res: movie_res.get('year') == year, results)
                    if len(results) > 1 and results[0].get('title') != title:
                        exact_matches = filter(lambda movie_res: movie_res.get('title') == title, results)
                        if len(exact_matches) > 0:
                            results = exact_matches
                    if len(results) > 0:
                        result = results[0]
                        movie = session.query(RottenTomatoesMovie).filter(RottenTomatoesMovie.id == result.get('id')).first()
                        if not movie:
                            movie = RottenTomatoesMovie(result)
                            get_movie_details(movie, session)
                            session.merge(movie)
                        if title.lower() != movie.title.lower():
                            session.merge(RottenTomatoesSearchResult(search=search_string, movie=movie))
        except URLError:
            raise LookupError('Error looking up movie from RottenTomatoes')

    if not movie:
        raise LookupError('No results found from rotten tomatoes for %s' % id_str())
    else:
        # Access attributes to force the relationships to eager load before we detach from session
        movie.genres
        movie.posters
        return movie


def get_movie_details(movie, session, movie_data=None):
    """Populate details for this :movie: from Rotten Tomatoes"""

    if not movie_data:
        if not movie.id:
            raise LookupError('Cannot get rotten tomatoes details without rotten tomatoes id')
        movie_data = movies_info(movie.id)
    if movie_data:
        movie.update_from_dict(movie_data)
        movie.update_from_dict(movie_data.get('ratings'))
        genres = movie_data.get('genres')
        if genres:
            for name in genres:
                genre = session.query(RottenTomatoesGenre).filter(func.lower(RottenTomatoesGenre.name) == name.lower()).first()
                if not genre:
                    genre = RottenTomatoesGenre(name)
                movie.genres.append(genre)
        release_dates = movie_data.get('release_dates')
        if release_dates:
            for name, date in release_dates.items():
                movie.release_dates.append(ReleaseDate(name, date))
        posters = movie_data.get('posters')
        if posters:
            for name, url in posters.items():
                movie.posters.append(RottenTomatoesPoster(name, url))
        cast = movie_data.get('abridged_cast')
        if cast:
            for actor in cast:
                movie.cast.append(RottenTomatoesActor(actor.get('name')))
        directors = movie_data.get('abridged_directors')
        if directors:
            for director in directors:
                movie.directors.append(RottenTomatoesDirector(director.get('name')))
        alternate_ids = movie_data.get('alternate_ids')
        if alternate_ids:
            for name, id in alternate_ids.items():
                movie.alternate_ids.append(RottenTomatoesAlternateId(name, id))
        links = movie_data.get('links')
        if links:
            for name, url in links.items():
                movie.links.append(RottenTomatoesLink(name, url))
        movie.updated = datetime.now()
    else:
        raise LookupError('No movie_datas for rottentomatoes_id %s' % movie.id)


def movies_info(id):
    url = '%s/%s/movies/%s.json?apikey=%s' % (SERVER, API_VER, id, API_KEY)
    result = get_json(url)
    if isinstance(result, dict) and result.get('id'):
        return result


def movies_alias(id, type='imdb'):
    if type == 'imdb':
        id = id.lstrip('t')
    url = '%s/%s/movie_alias.json?id=%s&type=%s' % (SERVER, API_VER, id, type)
    result = get_json(url)
    if isinstance(result, dict) and result.get('id'):
        return result


def movies_search(q, page_limit=None, page=None):
    if isinstance(q, basestring):
        q = q.replace(' ', '+').encode('utf-8')

    url = '%s/%s/movies.json?q=%s&apikey=%s' % (SERVER, API_VER, q, API_KEY)
    if page_limit:
        url += '&page_limit=%i' % (page_limit)
    if page:
        url += '&page=%i' % (page)

    result = get_json(url)
    if isinstance(result, dict) and result.get('total') and len(result.get('movies')):
        return result


def get_json(url):
    try:
        log.debug('fetching json at %s' % url)
        data = urlopener(url, log)
    except URLError, e:
        log.warning('Request failed %s' % url)
        return
    try:
        result = json.load(data)
    except ValueError:
        log.warning('Rotten Tomatoes returned invalid json.')
        return
    return result
