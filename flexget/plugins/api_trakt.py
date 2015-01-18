from __future__ import unicode_literals, division, absolute_import
from difflib import SequenceMatcher
import logging
import urllib
from urlparse import urljoin

import requests
from sqlalchemy import Table, Column, Integer, String, Unicode, Boolean, func, Date, DateTime
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema
from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.plugins.filter.series import normalize_series_name
from flexget.utils.database import with_session
from flexget.utils import json

api_key = '6c228565a45a302e49fb7d2dab066c9ab948b7be/'
search_show = 'http://api.trakt.tv/search/shows.json/'
episode_summary = 'http://api.trakt.tv/show/episode/summary.json/'
show_summary = 'http://api.trakt.tv/show/summary.json/'
Base = db_schema.versioned_base('api_trakt', 3)
log = logging.getLogger('api_trakt')
# Production Site
API_KEY = '57e188bcb9750c79ed452e1674925bc6848bd126e02bb15350211be74c6547af'
API_URL = 'https://api.trakt.tv/'


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
    session = Session()
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


class TraktContainer(object):

    def __init__(self, init_dict=None):
        if isinstance(init_dict, dict):
            self.update_from_dict(init_dict)

    def update_from_dict(self, update_dict):
        for col in self.__table__.columns:
            if isinstance(update_dict.get(col.name), (basestring, int, float)):
                setattr(self, col.name, update_dict[col.name])


class Genre(TraktContainer, Base):

    __tablename__ = 'trakt_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Unicode)
    slug = Column(Unicode) # Not sure if this is needed, depends on what is returned by genres from api calls

show_genres_table = Table('trakt_show_genres', Base.metadata,
                         Column('trakt_id', Integer, ForeignKey('trakt_series.trakt_id')),
                         Column('genre_id', Integer, ForeignKey('trakt_genres.id')))

movie_genres_table = Table('trakt_movie_genres', Base.metadata,
                          Column('trakt_id', Integer, ForeignKey('trakt_movies.trakt_id')),
                          Column('genre_id', Integer, ForeignKey('trakt_genres.id')))


class Actor(TraktContainer, Base):

    __tablename__ = 'trakt_actors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)


show_actors_table = Table('trakt_show_actors', Base.metadata,
                     Column('trakt_id', Integer, ForeignKey('trakt_series.trakt_id')),
                     Column('actors_id', Integer, ForeignKey('trakt_actors.id')))

movie_actors_table = Table('trakt_movie_actors', Base.metadata,
                     Column('trakt_id', Integer, ForeignKey('trakt_series.trakt_id')),
                     Column('actors_id', Integer, ForeignKey('trakt_actors.id')))



class Show(TraktContainer, Base):
    __tablename__ = 'trakt_series'

    trakt_id = Column(Integer, primary_key=True, autoincrement=False)
    trakt_slug = Column(Unicode)
    tvdb_id = Column(Integer)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    title = Column(Unicode)
    year = Column(Integer)
    genres = relation('Genre', secondary=show_genres_table)
    network = Column(Unicode, nullable=True)
    certification = Column(Unicode)
    country = Column(Unicode)
    overview = Column(Unicode)
    first_aired = Column(Integer)
    first_aired_iso = Column(Unicode)
    first_aired_utc = Column(Integer)
    air_day = Column(Unicode)
    air_day_utc = Column(Unicode)
    air_time = Column(Unicode)
    air_time_utc = Column(Unicode)
    runtime = Column(Integer)
    last_updated = Column(Integer)
    poster = Column(String)
    fanart = Column(String)
    banner = Column(String)
    status = Column(String)
    url = Column(Unicode)
    episodes = relation('Episode', backref='show', cascade='all, delete, delete-orphan')
    actors = relation('Actors', secondary=show_actors_table)

    def update(self, session):
        tvdb_id = self.tvdb_id
        url = ('%s%s%s' % (show_summary, api_key, tvdb_id))
        try:
            data = requests.get(url).json()
        except requests.RequestException as e:
            raise LookupError('Request failed %s' % url)
        if not data or not data.get('title'):
            raise LookupError('Could not update database info from trakt for tvdb id `%s`' % tvdb_id)
        if data['images']:
            data.update(data['images'])
        if data['genres']:
            genres = {}
            for genre in data['genres']:
                db_genre = session.query(TraktGenre).filter(TraktGenre.name == genre).first()
                if not db_genre:
                    genres['name'] = genre
                    db_genre = TraktGenre(genres)
                if db_genre not in self.genre:
                    self.genre.append(db_genre)
        if data['people']['actors']:
            series_actors = data['people']['actors']
            for i in series_actors:
                if i['name']:
                    db_character = session.query(TraktActors).filter(TraktActors.name == i['name']).first()
                    if not db_character:
                        db_character = TraktActors(i)
                    if db_character not in self.actors:
                        self.actors.append(db_character)
        TraktContainer.update_from_dict(self, data)

    def __repr__(self):
        return '<Traktv Name=%s, TVDB_ID=%s>' % (self.title, self.tvdb_id)


class Episode(TraktContainer, Base):
    __tablename__ = 'trakt_episodes'

    trakt_id = Column(Integer, primary_key=True, autoincrement=False)
    tvdb_id = Column(Integer)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    title = Column(Unicode)
    season = Column(Integer)
    number = Column(Integer)
    nummber_abs = Column(Integer)
    overview = Column(Unicode)
    first_aired = Column(DateTime)

    series_id = Column(Integer, ForeignKey('trakt_series.trakt_id'), nullable=False)


class Movie(TraktContainer, Base):
    __tablename__ = 'trakt_movies'

    trakt_id = Column(Integer, primary_key=True, autoincrement=False)
    trakt_slug = Column(Unicode)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tagline = Column(Unicode)
    overview = Column(Unicode)
    released = Column(Date)
    runtime = Column(Integer)
    rating = Column(Integer)
    votes = Column(Integer)
    language = Column(Unicode)
    genres = relation('Genre', secondary=movie_genres_table)
    actors = relation('Actors', secondary=movie_actors_table)


def get_series_id(title):
    norm_series_name = normalize_series_name(title)
    series_name = urllib.quote_plus(norm_series_name)
    url = search_show + api_key + series_name
    series = None
    try:
        response = requests.get(url)
    except requests.RequestException:
        log.warning('Request failed %s' % url)
        return
    try:
        data = response.json()
    except ValueError:
        raise LookupError('Error Parsing Traktv Json for %s' % title)
    if 'error' in data:
        raise LookupError('Error from trakt: %s' % data['error'])
    for item in data:
        if normalize_series_name(item['title']) == norm_series_name:
            series = item['tvdb_id']
            break
    else:
        for item in data:
            title_match = SequenceMatcher(lambda x: x in '\t',
                                          normalize_series_name(item['title']), norm_series_name).ratio()
            if title_match > .9:
                log.debug('Warning: Using lazy matching because title was not found exactly for %s' % title)
                series = item['tvdb_id']
                break
    if not series:
        raise LookupError('Could not find tvdb_id for `%s` on trakt' % title)
    return series


class ApiTrakt(object):

    @staticmethod
    @with_session
    def lookup_show(trakt_id, only_cached=False, session=None):
        series = None

        def id_str():
            return '<name=%s, tvdb_id=%s>' % (title, tvdb_id)
        if tvdb_id:
            series = session.query(Series).filter(Series.tvdb_id == tvdb_id).first()
        if not series and title:
            series = session.query(Series).filter(func.lower(Series.title) == title.lower()).first()
            if not series:
                found = session.query(TraktSearchResult).filter(func.lower(TraktSearchResult.search) ==
                                                                title.lower()).first()
                if found and found.series:
                    series = found.series
        if not series:
            if only_cached:
                raise LookupError('Series %s not found from cache' % id_str())
            log.debug('Series %s not found in cache, looking up from trakt.' % id_str())
            if tvdb_id:
                series = Series()
                series.tvdb_id = tvdb_id
                series.update(session=session)
                session.add(series)
            elif title:
                series_lookup = get_series_id(title)
                if series_lookup:
                    series = session.query(Series).filter(Series.tvdb_id == series_lookup).first()
                    if not series:
                        series = Series()
                        series.tvdb_id = series_lookup
                        series.update(session=session)
                        session.add(series)
                    if title.lower() != series.title.lower():
                        session.add(TraktSearchResult(search=title, series=series))

        if not series:
            raise LookupError('No results found from traktv for %s' % id_str())

        # Make sure relations are loaded before returning
        series.episodes
        series.genre
        series.actors
        return series

    @staticmethod
    @with_session
    def lookup_episode(title=None, seasonnum=None, episodenum=None, tvdb_id=None, session=None, only_cached=False):
        series = ApiTrakt.lookup_series(title=title, tvdb_id=tvdb_id, only_cached=only_cached, session=session)
        if not series:
            raise LookupError('Could not identify series')
        ep_description = '%s.S%sE%s' % (series.title, seasonnum, episodenum)
        episode = session.query(Episode).filter(Episode.series_id == series.tvdb_id).\
            filter(Episode.season == seasonnum).filter(Episode.number == episodenum).first()
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
            episode = session.query(Episode).filter(Episode.tvdb_id == ep_data['tvdb_id']).first()
            if not episode:
                # Update result into format TraktEpisode expects (?)
                ep_data['episode_name'] = ep_data.pop('title')
                ep_data.update(ep_data['images'])
                del ep_data['images']

                episode = Episode(ep_data)
                series.episodes.append(episode)
                session.merge(episode)

        return episode


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTrakt, 'api_trakt', api_ver=2)
