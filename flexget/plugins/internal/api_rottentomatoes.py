import difflib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Type
from urllib.error import URLError
from urllib.parse import quote_plus

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Table, func, sql
from sqlalchemy.orm import relation, Session
from sqlalchemy.schema import ForeignKey, Index

from flexget import db_schema, plugin
from flexget.plugin import PluginError, internet
from flexget.utils import requests
from flexget.utils.database import text_date_synonym, with_session
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema

logger = logger.bind(name='api_rottentomatoes')
Base: Type[db_schema.VersionedBaseMeta] = db_schema.versioned_base('api_rottentomatoes', 2)
session = requests.Session()
# There is a 5 call per second rate limit per api key with multiple users on the same api key, this can be problematic
session.add_domain_limiter(requests.TimedLimiter('api.rottentomatoes.com', '0.4 seconds'))

# This is developer Atlanta800's API key
API_KEY = 'rh8chjzp8vu6gnpwj88736uv'
API_VER = 'v1.0'
SERVER = 'http://api.rottentomatoes.com/api/public'

MIN_MATCH = 0.5
MIN_DIFF = 0.01


@db_schema.upgrade('api_rottentomatoes')
def upgrade(ver: int, session: Session) -> int:
    if ver == 0:
        table_names = [
            'rottentomatoes_actors',
            'rottentomatoes_alternate_ids',
            'rottentomatoes_directors',
            'rottentomatoes_genres',
            'rottentomatoes_links',
            'rottentomatoes_movie_actors',
            'rottentomatoes_movie_directors',
            'rottentomatoes_movie_genres',
            'rottentomatoes_movies',
            'rottentomatoes_posters',
            'rottentomatoes_releasedates',
            'rottentomatoes_search_results',
        ]
        tables = [table_schema(name, session) for name in table_names]
        for table in tables:
            session.execute(table.delete())
        table_add_column('rottentomatoes_actors', 'rt_id', String, session)
        ver = 1
    if ver == 1:
        table = table_schema('rottentomatoes_search_results', session)
        session.execute(sql.delete(table, table.c.movie_id == None))
        ver = 2
    return ver


# association tables
genres_table = Table(
    'rottentomatoes_movie_genres',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('rottentomatoes_movies.id')),
    Column('genre_id', Integer, ForeignKey('rottentomatoes_genres.id')),
    Index('ix_rottentomatoes_movie_genres', 'movie_id', 'genre_id'),
)
Base.register_table(genres_table)

actors_table = Table(
    'rottentomatoes_movie_actors',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('rottentomatoes_movies.id')),
    Column('actor_id', Integer, ForeignKey('rottentomatoes_actors.id')),
    Index('ix_rottentomatoes_movie_actors', 'movie_id', 'actor_id'),
)
Base.register_table(actors_table)

directors_table = Table(
    'rottentomatoes_movie_directors',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('rottentomatoes_movies.id')),
    Column('director_id', Integer, ForeignKey('rottentomatoes_directors.id')),
    Index('ix_rottentomatoes_movie_directors', 'movie_id', 'director_id'),
)
Base.register_table(directors_table)


# TODO: get rid of
class RottenTomatoesContainer:
    """Base class for RottenTomatoes objects"""

    def __init__(self, init_dict: Optional[Dict[str, Any]] = None) -> None:
        if isinstance(init_dict, dict):
            self.update_from_dict(init_dict)

    def update_from_dict(self, update_dict: Dict[str, Any]) -> None:
        """Populates any simple (string or number) attributes from a dict"""
        for col in self.__table__.columns:
            if isinstance(update_dict.get(col.name), (str, int, float)):
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
    posters = relation(
        'RottenTomatoesPoster', backref='movie', cascade='all, delete, delete-orphan'
    )
    cast = relation('RottenTomatoesActor', secondary=actors_table, backref='movies')
    directors = relation('RottenTomatoesDirector', secondary=directors_table, backref='movies')
    studio = Column(String)
    # NOTE: alternate_ids is not anymore used, it used to store imdb_id
    alternate_ids = relation(
        'RottenTomatoesAlternateId', backref='movie', cascade='all, delete, delete-orphan'
    )
    links = relation('RottenTomatoesLink', backref='movie', cascade='all, delete, delete-orphan')

    # updated time, so we can grab new rating counts after 48 hours
    # set a default, so existing data gets updated with a rating
    updated = Column(DateTime)

    @property
    def expired(self) -> bool:
        """
        :return: True if movie details are considered to be expired, ie. need of update
        """
        if self.updated is None:
            logger.debug('updated is None: {}', self)
            return True
        refresh_interval = 2
        if self.year:
            age = datetime.now().year - self.year
            refresh_interval += age * 5
            logger.debug('movie `{}` age {} expires in {} days', self.title, age, refresh_interval)
        return self.updated < datetime.now() - timedelta(days=refresh_interval)

    def __repr__(self) -> str:
        return '<RottenTomatoesMovie(title=%s,id=%s,year=%s)>' % (self.title, self.id, self.year)


class RottenTomatoesGenre(Base):
    __tablename__ = 'rottentomatoes_genres'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name: str) -> None:
        self.name = name


class ReleaseDate(Base):
    __tablename__ = 'rottentomatoes_releasedates'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    date = text_date_synonym('_date')
    _date = Column('date', DateTime)

    def __init__(self, name: str, date: datetime) -> None:
        self.name = name
        self.date = date


class RottenTomatoesPoster(Base):
    __tablename__ = 'rottentomatoes_posters'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    url = Column(String)

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url


class RottenTomatoesActor(Base):
    __tablename__ = 'rottentomatoes_actors'

    id = Column(Integer, primary_key=True)
    rt_id = Column(String)
    name = Column(String)

    def __init__(self, name: str, rt_id: str) -> None:
        self.name = name
        self.rt_id = rt_id


class RottenTomatoesDirector(Base):
    __tablename__ = 'rottentomatoes_directors'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name: str) -> None:
        self.name = name


class RottenTomatoesAlternateId(Base):
    __tablename__ = 'rottentomatoes_alternate_ids'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    id = Column(String)

    def __init__(self, name: str, id: str) -> None:
        self.name = name
        self.id = id


class RottenTomatoesLink(Base):
    __tablename__ = 'rottentomatoes_links'

    db_id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'))
    name = Column(String)
    url = Column(String)

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url


class RottenTomatoesSearchResult(Base):
    __tablename__ = 'rottentomatoes_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(String, nullable=False)
    movie_id = Column(Integer, ForeignKey('rottentomatoes_movies.id'), nullable=False)
    movie = relation(RottenTomatoesMovie, backref='search_strings')

    def __repr__(self) -> str:
        return '<RottenTomatoesSearchResult(search=%s,movie_id=%s,movie=%s)>' % (
            self.search,
            self.movie_id,
            self.movie,
        )


@internet(logger)
@with_session
def lookup_movie(
    title: Optional[str] = None,
    year: Optional[int] = None,
    rottentomatoes_id: Optional[int] = None,
    smart_match: Optional[bool] = None,
    only_cached: bool = False,
    session: Optional[Session] = None,
    api_key: Optional[str] = None,
) -> RottenTomatoesMovie:
    """
    Do a lookup from Rotten Tomatoes for the movie matching the passed arguments.
    Any combination of criteria can be passed, the most specific criteria specified will be used.

    :param rottentomatoes_id: rottentomatoes_id of desired movie
    :param string title: title of desired movie
    :param year: release year of desired movie
    :param smart_match: attempt to clean and parse title and year from a string
    :param only_cached: if this is specified, an online lookup will not occur if the movie is not in the cache
    :param session: optionally specify a session to use, if specified, returned Movie will be live in that session
    :param api_key: optionaly specify an API key to use
    :returns: The Movie object populated with data from Rotten Tomatoes
    :raises: PluginError if a match cannot be found or there are other problems with the lookup
    """
    if smart_match:
        # If smart_match was specified, and we don't have more specific criteria, parse it into a title and year
        title_parser = plugin.get('parsing', 'api_rottentomatoes').parse_movie(smart_match)
        title = title_parser.name
        year = title_parser.year
        if title == '' and not (rottentomatoes_id or title):
            raise PluginError('Failed to parse name from %s' % smart_match)

    search_string = ""
    if title:
        search_string = title.lower()
        if year:
            search_string = '%s %s' % (search_string, year)
    elif not rottentomatoes_id:
        raise PluginError('No criteria specified for rotten tomatoes lookup')

    def id_str() -> str:
        return f'<title={title},year={year},rottentomatoes_id={rottentomatoes_id}>'

    logger.debug('Looking up rotten tomatoes information for {}', id_str())

    movie = None

    # Try to lookup from cache
    if rottentomatoes_id:
        movie = (
            session.query(RottenTomatoesMovie)
            .filter(RottenTomatoesMovie.id == rottentomatoes_id)
            .first()
        )
    if not movie and title:
        movie_filter = session.query(RottenTomatoesMovie).filter(
            func.lower(RottenTomatoesMovie.title) == title.lower()
        )
        if year:
            movie_filter = movie_filter.filter(RottenTomatoesMovie.year == year)
        movie = movie_filter.first()
        if not movie:
            logger.debug('No matches in movie cache found, checking search cache.')
            found = (
                session.query(RottenTomatoesSearchResult)
                .filter(func.lower(RottenTomatoesSearchResult.search) == search_string)
                .first()
            )
            if found and found.movie:
                logger.debug('Movie found in search cache.')
                movie = found.movie
    if movie:
        # Movie found in cache, check if cache has expired.
        if movie.expired and not only_cached:
            logger.debug(
                'Cache has expired for {}, attempting to refresh from Rotten Tomatoes.', id_str()
            )
            try:
                result = movies_info(movie.id, api_key)
                movie = _set_movie_details(movie, session, result, api_key)
                session.merge(movie)
            except URLError:
                logger.error(
                    'Error refreshing movie details from Rotten Tomatoes, cached info being used.'
                )
        else:
            logger.debug('Movie {} information restored from cache.', id_str())
    else:
        if only_cached:
            raise PluginError('Movie %s not found from cache' % id_str())
        # There was no movie found in the cache, do a lookup from Rotten Tomatoes
        logger.debug('Movie {} not found in cache, looking up from rotten tomatoes.', id_str())
        try:
            if not movie and rottentomatoes_id:
                result = movies_info(rottentomatoes_id, api_key)
                if result:
                    movie = RottenTomatoesMovie()
                    movie = _set_movie_details(movie, session, result, api_key)
                    session.add(movie)

            if not movie and title:
                # TODO: Extract to method
                logger.verbose('Searching from rt `{}`', search_string)
                results = movies_search(search_string, api_key=api_key)
                if results:
                    results = results.get('movies')
                    if results:
                        for movie_res in results:
                            seq = difflib.SequenceMatcher(
                                lambda x: x == ' ', movie_res['title'].lower(), title.lower()
                            )
                            movie_res['match'] = seq.ratio()
                        results.sort(key=lambda x: x['match'], reverse=True)

                        # Remove all movies below MIN_MATCH, and different year
                        for movie_res in results[:]:

                            if year and movie_res.get('year'):
                                movie_res['year'] = int(movie_res['year'])
                                if movie_res['year'] != year:
                                    release_year = False
                                    if movie_res.get('release_dates', {}).get('theater'):
                                        logger.debug('Checking year against theater release date')
                                        release_year = time.strptime(
                                            movie_res['release_dates'].get('theater'), '%Y-%m-%d'
                                        ).tm_year
                                    elif movie_res.get('release_dates', {}).get('dvd'):
                                        logger.debug('Checking year against dvd release date')
                                        release_year = time.strptime(
                                            movie_res['release_dates'].get('dvd'), '%Y-%m-%d'
                                        ).tm_year
                                    if not (release_year and release_year == year):
                                        logger.debug(
                                            'removing {} - {} (wrong year: {})',
                                            movie_res['title'],
                                            movie_res['id'],
                                            str(release_year or movie_res['year']),
                                        )
                                        results.remove(movie_res)
                                        continue
                            if movie_res['match'] < MIN_MATCH:
                                logger.debug('removing {} (min_match)', movie_res['title'])
                                results.remove(movie_res)
                                continue

                        if not results:
                            raise PluginError('no appropiate results')

                        if len(results) == 1:
                            logger.debug('SUCCESS: only one movie remains')
                        else:
                            # Check min difference between best two hits
                            diff = results[0]['match'] - results[1]['match']
                            if diff < MIN_DIFF:
                                logger.debug(
                                    'unable to determine correct movie, min_diff too small(`{} ({}) - {}` <-?-> `{} ({}) - {}`)',
                                    results[0]['title'],
                                    results[0]['year'],
                                    results[0]['id'],
                                    results[1]['title'],
                                    results[1]['year'],
                                    results[1]['id'],
                                )
                                for r in results:
                                    logger.debug(
                                        'remain: {} (match: {}) {}',
                                        r['title'],
                                        r['match'],
                                        r['id'],
                                    )
                                raise PluginError('min_diff')

                        result = movies_info(results[0].get('id'), api_key)

                        if not result:
                            result = results[0]

                        movie = (
                            session.query(RottenTomatoesMovie)
                            .filter(RottenTomatoesMovie.id == result['id'])
                            .first()
                        )

                        if not movie:
                            movie = RottenTomatoesMovie()
                            movie = _set_movie_details(movie, session, result, api_key)
                            session.add(movie)
                            session.commit()

                        if title.lower() != movie.title.lower():
                            logger.debug("Saving search result for '{}'", search_string)
                            session.add(
                                RottenTomatoesSearchResult(search=search_string, movie=movie)
                            )
        except URLError:
            raise PluginError('Error looking up movie from RottenTomatoes')

    if not movie:
        raise PluginError('No results found from rotten tomatoes for %s' % id_str())
    else:
        # Access attributes to force the relationships to eager load before we detach from session
        for attr in [
            'alternate_ids',
            'cast',
            'directors',
            'genres',
            'links',
            'posters',
            'release_dates',
        ]:
            getattr(movie, attr)
        session.commit()
        return movie


# TODO: get rid of or heavily refactor
def _set_movie_details(
    movie: RottenTomatoesMovie,
    session: Session,
    movie_data: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> Any:
    """
    Populate ``movie`` object from given data

    :param movie: movie object to update
    :param session: session to use, returned Movie will be live in that session
    :param api_key: optionally specify an API key to use
    :param movie_data: data to copy into the :movie:
    """

    if not movie_data:
        if not movie.id:
            raise PluginError('Cannot get rotten tomatoes details without rotten tomatoes id')
        movie_data = movies_info(movie.id, api_key)
    if movie_data:
        if movie.id:
            logger.debug(
                "Updating movie info (actually just deleting the old info and adding the new)"
            )
            del movie.release_dates[:]
            del movie.posters[:]
            del movie.alternate_ids[:]
            del movie.links[:]
        movie.update_from_dict(movie_data)
        movie.update_from_dict(movie_data.get('ratings'))
        genres = movie_data.get('genres')
        if genres:
            for name in genres:
                genre = (
                    session.query(RottenTomatoesGenre)
                    .filter(func.lower(RottenTomatoesGenre.name) == name.lower())
                    .first()
                )
                if not genre:
                    genre = RottenTomatoesGenre(name)
                movie.genres.append(genre)
        release_dates = movie_data.get('release_dates')
        if release_dates:
            for name, date in list(release_dates.items()):
                movie.release_dates.append(ReleaseDate(name, date))
        posters = movie_data.get('posters')
        if posters:
            for name, url in list(posters.items()):
                movie.posters.append(RottenTomatoesPoster(name, url))
        cast = movie_data.get('abridged_cast')
        if cast:
            for res_actor in cast:
                actor = (
                    session.query(RottenTomatoesActor)
                    .filter(func.lower(RottenTomatoesActor.rt_id) == res_actor['id'])
                    .first()
                )
                if not actor:
                    actor = RottenTomatoesActor(res_actor['name'], res_actor['id'])
                movie.cast.append(actor)
        directors = movie_data.get('abridged_directors')
        if directors:
            for res_director in directors:
                director = (
                    session.query(RottenTomatoesDirector)
                    .filter(
                        func.lower(RottenTomatoesDirector.name) == res_director['name'].lower()
                    )
                    .first()
                )
                if not director:
                    director = RottenTomatoesDirector(res_director['name'])
                movie.directors.append(director)
        alternate_ids = movie_data.get('alternate_ids')
        if alternate_ids:
            for name, id in list(alternate_ids.items()):
                movie.alternate_ids.append(RottenTomatoesAlternateId(name, id))
        links = movie_data.get('links')
        if links:
            for name, url in list(links.items()):
                movie.links.append(RottenTomatoesLink(name, url))
        movie.updated = datetime.now()
    else:
        raise PluginError('No movie_data for rottentomatoes_id %s' % movie.id)

    return movie


def movies_info(id, api_key: Optional[str] = None):
    if not api_key:
        api_key = API_KEY
    url = f'{SERVER}/{API_VER}/movies/{id}.json?apikey={api_key}'
    result = get_json(url)
    if isinstance(result, dict) and result.get('id'):
        return result


def lists(
    list_type,
    list_name,
    limit: int = 20,
    page_limit: int = 20,
    page: Optional[int] = None,
    api_key=None,
):
    if isinstance(list_type, str):
        list_type = list_type.replace(' ', '_')
    if isinstance(list_name, str):
        list_name = list_name.replace(' ', '_')

    if not api_key:
        api_key = API_KEY

    url = f'{SERVER}/{API_VER}/lists/{list_type}/{list_name}.json?apikey={api_key}'
    if limit:
        url += f'&limit={limit}'
    if page_limit:
        url += f'&page_limit={page_limit}'
    if page:
        url += f'&page={page}'

    results = get_json(url)
    if isinstance(results, dict) and len(results.get('movies')):
        return results


def movies_search(
    q, page_limit: Optional[int] = None, page: Optional[int] = None, api_key: Optional[str] = None
):
    if isinstance(q, str):
        q = quote_plus(q.encode('latin-1', errors='ignore'))

    if not api_key:
        api_key = API_KEY

    url = f'{SERVER}/{API_VER}/movies.json?q={q}&apikey={api_key}'
    if page_limit:
        url += f'&page_limit={page_limit}'
    if page:
        url += f'&page={page}'

    results = get_json(url)
    if isinstance(results, dict) and results.get('total') and results.get('movies'):
        return results


def get_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        logger.debug('fetching json at {}', url)
        data = session.get(url)
        return data.json()
    except requests.RequestException as e:
        logger.warning('Request failed {}: {}', url, e)
        return None
    except ValueError:
        logger.warning('Rotten Tomatoes returned invalid json at: {}', url)
        return None
