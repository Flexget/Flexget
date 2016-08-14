from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime, timedelta
import time

from sqlalchemy import Table, Column, Integer, Float, Unicode, DateTime, func
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from dateutil.parser import parse as dateutil_parse

from flexget import db_schema, plugin
from flexget.utils.soup import get_soup
from flexget.event import event
from flexget.plugin import get_plugin_by_name
from flexget.utils import requests
from flexget.utils.database import text_date_synonym, year_property

log = logging.getLogger('api_bluray')
Base = db_schema.versioned_base('api_bluray', 0)

# association tables
genres_table = Table('bluray_movie_genres', Base.metadata,
                     Column('movie_id', Integer, ForeignKey('bluray_movies.id')),
                     Column('genre_id', Integer, ForeignKey('bluray_genres.id')))
Base.register_table(genres_table)

BASE_URL = 'http://m.blu-ray.com/'


def bluray_request(endpoint, **params):
    full_url = BASE_URL + endpoint
    cookies = {
        'country': 'all',
        'listlayout_7': 'full',
        'search_section': 'bluraymovies'
    }
    return requests.get(full_url, params=params).json()


class BlurayMovie(Base):
    __tablename__ = 'bluray_movies'

    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    name = Column(Unicode)
    url = Column(Unicode)
    _release_date = Column('release_date', DateTime)
    release_date = text_date_synonym('_release_date')
    url = Column(Unicode)
    year = year_property('released')
    runtime = Column(Integer)
    overview = Column(Unicode)
    language = Column(Unicode)
    country = Column(Unicode)
    studio = Column(Unicode)
    rating = Column(Float)
    bluray_rating = Column(Integer)
    certification = Column(Unicode)
    _genres = relation('BlurayGenre', secondary=genres_table, backref='movies')
    genres = association_proxy('_genres', 'name')
    updated = Column(DateTime, default=datetime.now, nullable=False)

    def __init__(self, title, year):
        params = {
            'search': 'bluraymovies',
            'country': 'ALL',
            'keyword': title,
            '_': str(int(time.time() * 1000))
        }

        country_params = {'_': params['_']}
        try:
            search_results = bluray_request('quicksearch/search.php', **params)['items']
            countries = bluray_request('countries.json.php', **country_params) or {}

            if not search_results:
                raise LookupError('No search results found for {} on blu-ray.com'.format(title))

            search_results = sorted(search_results, key=lambda k: dateutil_parse(k['reldate'] or 'Dec 31'))
        except requests.RequestException as e:
            raise LookupError('Error searching for {} on blu-ray.com: {}'.format(title, e))

        # Simply take the first result unless year does not match
        for result in search_results:
            self.id = result['url'].split('/')[-1]
            self.name = result['title']
            flag = result['flag']
            country_code = flag.split('/')[-1].split('.')[0].lower()  # eg. http://some/url/UK.png -> uk
            # find country based on flag url, default United States
            country = 'United States'
            for c in countries['countries']:
                if c['c'].lower() == country_code:
                    country = c['n']
            self.country = country
            self.release_date = dateutil_parse(result['reldate'])
            self.bluray_rating = int(result['rating']) if result['rating'] else None

            # Used for parsing some more data, sadly with soup
            self.url = result['url']

            movie_info_response = requests.get(self.url).content

            movie_info = get_soup(movie_info_response)

            # rating col
            self.rating = float(movie_info.find('div', id='ratingscore').text.strip())

            # Third onecol_content contains some information we want
            onecol_content = movie_info.find_all('div', attrs={'class': 'onecol_content'})[2]

            # overview, genres etc
            contents = onecol_content.find('div').find('div')

            self.overview = contents.find('p').text.strip()

            # genres
            genres_content = contents.find('table').find_all('tr')

            genres = set()
            for genre in genres_content:
                genres.add(genre.find('td').text.strip())
            self._genres = [BlurayGenre(name=genre) for genre in genres]
            break


class BlurayGenre(Base):
    __tablename__ = 'bluray_genres'

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(Unicode, nullable=False)


class BluraySearchResult(Base):
    __tablename__ = 'bluray_search_results'

    search = Column(Unicode, primary_key=True)
    movie_id = Column(Integer, ForeignKey('bluray_movies.id'), nullable=True)
    movie = relation(BlurayMovie)

    def __init__(self, search, movie_id=None, movie=None):
        self.search = search.lower()
        if movie_id:
            self.movie_id = movie_id
        if movie:
            self.movie = movie


class ApiBluray(object):
    """Does lookups to Blu-ray.com and provides movie information. Caches lookups."""

    @staticmethod
    def estimate_release(title, year=None, session=None):
        #releasetimestampdesc
        pass

    @staticmethod
    def lookup(title=None, year=None, only_cached=False, session=None):
        if not title:
            raise LookupError('No criteria specified for blu-ray.com lookup')
        title_year = title + ' ({})'.format(year) if year else title

        movie_filter = session.query(BlurayMovie).filter(func.lower(BlurayMovie.name) == title.lower())
        if year:
            movie_filter = movie_filter.filter(BlurayMovie.year == year)
        movie = movie_filter.first()
        if not movie:
            search_string = title + ' ({})'.format(year) if year else ''
            found = session.query(BluraySearchResult). \
                filter(BluraySearchResult.search == search_string.lower()).first()
            if found and found.movie:
                movie = found.movie

        if movie:
            # Movie found in cache, check if cache has expired. Shamefully stolen from api_tmdb
            refresh_time = timedelta(days=2)
            if movie.released:
                if movie.released > datetime.now() - timedelta(days=7):
                    # Movie is less than a week old, expire after 1 day
                    refresh_time = timedelta(days=1)
                else:
                    age_in_years = (datetime.now() - movie.released).days / 365
                    refresh_time += timedelta(days=age_in_years * 5)
            if movie.updated < datetime.now() - refresh_time and not only_cached:
                log.debug('Cache has expired for %s, attempting to refresh from blu-ray.com.', movie.name)
                try:
                    updated_movie = BlurayMovie(title=title, year=year)
                except LookupError:
                    log.error('Error refreshing movie details for %s from blu-ray.com, cached info being used.',
                              title)
                else:
                    movie = session.merge(updated_movie)
            else:
                log.debug('Movie %s information restored from cache.', movie.name)
        else:
            if only_cached:
                raise LookupError('Movie %s not found from cache' % title_year)
            # There was no movie found in the cache, do a lookup from blu-ray.com
            log.verbose('Searching from blu-ray.com title=%s', title)

            # Add/merge movie to db
            movie = BlurayMovie(title=title, year=year)
            session.merge(movie)

            # Add to search results table if necessary
            if title.lower() != movie.name.lower():
                session.add(BluraySearchResult(search=title.lower(), movie_id=movie.id, movie=movie))

            if not movie:
                raise LookupError('Unable to find movie on blu-ray: {}'.format(title_year))

        return movie


@event('plugin.register')
def register_plugin():
    plugin.register(BlurayMovie, 'api_bluray', api_ver=2)
