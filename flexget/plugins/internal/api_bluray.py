import time
from datetime import date, datetime, timedelta
from json.decoder import JSONDecodeError
from typing import Any, Dict, Optional

from dateutil.parser import parse as dateutil_parse
from loguru import logger
from sqlalchemy import Column, Date, DateTime, Float, Integer, Table, Unicode, func
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Session, relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema, plugin
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils import requests
from flexget.utils.database import year_property
from flexget.utils.soup import get_soup

logger = logger.bind(name='api_bluray')
Base = db_schema.versioned_base('api_bluray', 0)

# association tables
genres_table = Table(
    'bluray_movie_genres',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('bluray_movies.id')),
    Column('genre_name', Integer, ForeignKey('bluray_genres.name')),
)
Base.register_table(genres_table)

BASE_URL = 'http://m.blu-ray.com/'


def bluray_request(endpoint, **params) -> Any:
    full_url = BASE_URL + endpoint
    response = requests.get(full_url, params=params)
    if response.content:
        try:
            return response.json(strict=False)
        except JSONDecodeError:
            raise PluginError('Could decode json from response blu-ray api')


def extract_release_date(bluray_entry: Dict[str, Any]) -> date:
    release_date = bluray_entry.get('reldate')
    if not release_date or release_date.lower() == 'no release date':
        try:
            year = int(bluray_entry.get('year'))
        except (TypeError, ValueError):
            pass
        else:
            return date(year, 12, 31)
        return datetime.now().date().replace(month=12, day=31)
    return dateutil_parse(release_date).date()


class BlurayMovie(Base):
    __tablename__ = 'bluray_movies'

    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    name = Column(Unicode)
    url = Column(Unicode)
    release_date = Column(Date)
    year = year_property('release_date')
    runtime = Column(Integer)
    overview = Column(Unicode)
    country = Column(Unicode)
    studio = Column(Unicode)
    rating = Column(Float)
    bluray_rating = Column(Integer)
    certification = Column(Unicode)
    _genres = relation('BlurayGenre', secondary=genres_table, backref='movies')
    genres = association_proxy('_genres', 'name')
    updated = Column(DateTime, default=datetime.now, nullable=False)

    def __init__(self, title: str, year: Optional[int]) -> None:
        if year:
            title_year = f'{title} ({year})'
        else:
            title_year = title

        params = {
            'section': 'bluraymovies',
            'country': 'ALL',
            'keyword': title,
            '_': str(int(time.time() * 1000)),
        }

        country_params = {'_': params['_']}
        try:
            response = bluray_request('quicksearch/search.php', **params)

            if not response or 'items' not in response:
                raise LookupError(f'No search results found for {title_year} on blu-ray.com')

            search_results = response['items']
            countries = bluray_request('countries.json.php', **country_params) or {}

            search_results = sorted(search_results, key=lambda k: extract_release_date(k))
        except requests.RequestException as e:
            raise LookupError(f'Error searching for {title_year} on blu-ray.com: {e}')

        # Simply take the first result unless year does not match
        for result in search_results:
            if year and str(year) != result['year']:
                continue

            self.id = int(result['url'].split('/')[-2])
            self.name = result['title']

            flag = result['flag']
            country_code = (
                flag.split('/')[-1].split('.')[0].lower()
            )  # eg. http://some/url/UK.png -> uk
            # find country based on flag url, default United States
            country = 'United States'
            for c in countries['countries']:
                if c['c'].lower() == country_code:
                    country = c['n']
            self.country = country
            self.release_date = extract_release_date(result)
            self.bluray_rating = int(result['rating']) if result['rating'] else None

            # Used for parsing some more data, sadly with soup
            self.url = result['url']

            try:
                movie_info_response = requests.get(self.url).content
            except (requests.RequestException, ConnectionError):
                raise LookupError("Couldn't connect to blu-ray.com. %s" % self.url)

            movie_info = get_soup(movie_info_response)

            # runtime and rating, should be the last span tag with class subheading
            bluray_info = movie_info.find('div', attrs={'class': 'bluray'})
            bluray_info = bluray_info.find_all('span', attrs={'class': 'subheading'})[
                -1
            ].text.split('|')

            self.studio = bluray_info[0].strip()

            for info in bluray_info[1:]:
                if 'min' in info:
                    self.runtime = int(info.replace('min', '').strip())
                elif 'Rated' in info:
                    self.certification = info.replace('Rated', '').strip()

            # rating
            rating_tag = movie_info.find('div', id='ratingscore')
            self.rating = float(rating_tag.text.strip()) if rating_tag else None

            # Third onecol_content contains some information we want
            onecol_content = movie_info.find_all('div', attrs={'class': 'onecol_content'})[2]

            # overview, genres etc
            contents = onecol_content.find('div').find('div')

            overview_tag = contents.find('p')
            self.overview = overview_tag.text.strip() if overview_tag else None

            # genres
            genres_table = contents.find('table')
            if not genres_table:
                break

            genres_content = genres_table.find_all('tr')
            if not genres_content:
                break

            genres = set()
            for genre in genres_content:
                genres.add(genre.find('td').text.strip())
            self._genres = [BlurayGenre(name=genre) for genre in genres]
            break
        else:
            raise LookupError(f'No search results found for {title_year} on blu-ray.com')


class BlurayGenre(Base):
    __tablename__ = 'bluray_genres'

    name = Column(Unicode, primary_key=True, nullable=False)


class BluraySearchResult(Base):
    __tablename__ = 'bluray_search_results'

    search = Column(Unicode, primary_key=True)
    movie_id = Column(Integer, ForeignKey('bluray_movies.id'), nullable=True)
    movie = relation(BlurayMovie)

    def __init__(
        self, search: str, movie_id: Optional[int] = None, movie: Optional[BlurayMovie] = None
    ) -> None:
        self.search = search.lower()
        if movie_id:
            self.movie_id = movie_id
        if movie:
            self.movie = movie


class ApiBluray:
    """Does lookups to Blu-ray.com and provides movie information. Caches lookups."""

    @staticmethod
    def lookup(
        title: Optional[str] = None,
        year: Optional[int] = None,
        only_cached: bool = False,
        session: Optional[Session] = None,
    ):
        if not title:
            raise LookupError('No criteria specified for blu-ray.com lookup')
        title_year = title + f' ({year})' if year else title

        movie_filter = session.query(BlurayMovie).filter(
            func.lower(BlurayMovie.name) == title.lower()
        )
        if year:
            movie_filter = movie_filter.filter(BlurayMovie.year == year)
        movie = movie_filter.first()
        if not movie:
            found = (
                session.query(BluraySearchResult)
                .filter(BluraySearchResult.search == title_year.lower())
                .first()
            )
            if found and found.movie:
                movie = found.movie

        if movie:
            # Movie found in cache, check if cache has expired. Shamefully stolen from api_tmdb
            refresh_time = timedelta(days=2)
            if movie.release_date:
                if movie.release_date > datetime.now().date() - timedelta(days=7):
                    # Movie is less than a week old, expire after 1 day
                    refresh_time = timedelta(days=1)
                else:
                    age_in_years = (datetime.now().date() - movie.release_date).days / 365
                    refresh_time += timedelta(days=age_in_years * 5)
            if movie.updated < datetime.now() - refresh_time and not only_cached:
                logger.debug(
                    'Cache has expired for {}, attempting to refresh from blu-ray.com.', movie.name
                )
                try:
                    updated_movie = BlurayMovie(title=title, year=year)
                except LookupError as e:
                    logger.error(
                        'Error refreshing movie details for {} from blu-ray.com, cached info being used. {}',
                        title,
                        e,
                    )
                else:
                    movie = session.merge(updated_movie)
            else:
                logger.debug('Movie {} information restored from cache.', movie.name)
        else:
            if only_cached:
                raise LookupError('Movie %s not found from cache' % title_year)
            # There was no movie found in the cache, do a lookup from blu-ray.com
            logger.verbose('Searching from blu-ray.com `{}`', title)

            # Add/merge movie to db
            movie = BlurayMovie(title=title, year=year)

            # Add to search results table if necessary
            if title.lower() != movie.name.lower():
                session.add(BluraySearchResult(search=title_year.lower(), movie_id=movie.id))

            session.merge(movie)

            if not movie:
                raise LookupError(f'Unable to find movie on blu-ray: {title_year}')

        return movie


@event('plugin.register')
def register_plugin() -> None:
    plugin.register(ApiBluray, 'api_bluray', api_ver=2, interfaces=[])
