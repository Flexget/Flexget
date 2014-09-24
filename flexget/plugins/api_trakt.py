from __future__ import unicode_literals, division, absolute_import
from difflib import SequenceMatcher
import logging
import re
import urllib

import requests
from sqlalchemy import Table, Column, Integer, String, Unicode, Boolean, func
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema as schema
from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.series import normalize_series_name
from flexget.utils.database import with_session

api_key = '6c228565a45a302e49fb7d2dab066c9ab948b7be/'
search_show = 'http://api.trakt.tv/search/shows.json/'
episode_summary = 'http://api.trakt.tv/show/episode/summary.json/'
show_summary = 'http://api.trakt.tv/show/summary.json/'
Base = schema.versioned_base('api_trakt', 2)
log = logging.getLogger('api_trakt')


class TraktContainer(object):

    def __init__(self, init_dict=None):
        if isinstance(init_dict, dict):
            self.update_from_dict(init_dict)

    def update_from_dict(self, update_dict):
        for col in self.__table__.columns:
            if isinstance(update_dict.get(col.name), (basestring, int, float)):
                setattr(self, col.name, update_dict[col.name])

genres_table = Table('trakt_series_genres', Base.metadata,
                     Column('tvdb_id', Integer, ForeignKey('trakt_series.tvdb_id')),
                     Column('genre_id', Integer, ForeignKey('trakt_genres.id')))


class TraktGenre(TraktContainer, Base):

    __tablename__ = 'trakt_genres'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=True)

actors_table = Table('trakt_series_actors', Base.metadata,
                     Column('tvdb_id', Integer, ForeignKey('trakt_series.tvdb_id')),
                     Column('actors_id', Integer, ForeignKey('trakt_actors.id')))


class TraktActors(TraktContainer, Base):

    __tablename__ = 'trakt_actors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)


class TraktEpisode(TraktContainer, Base):
    __tablename__ = 'trakt_episodes'

    tvdb_id = Column(Integer, primary_key=True, autoincrement=False)
    episode_name = Column(Unicode)
    season = Column(Integer)
    number = Column(Integer)
    overview = Column(Unicode)
    expired = Column(Boolean)
    first_aired = Column(Integer)
    first_aired_iso = Column(Unicode)
    first_aired_utc = Column(Integer)
    screen = Column(Unicode)

    series_id = Column(Integer, ForeignKey('trakt_series.tvdb_id'), nullable=False)


class TraktSeries(TraktContainer, Base):
    __tablename__ = 'trakt_series'

    tvdb_id = Column(Integer, primary_key=True, autoincrement=False)
    tvrage_id = Column(Unicode)
    imdb_id = Column(Unicode)
    title = Column(Unicode)
    year = Column(Integer)
    genre = relation('TraktGenre', secondary=genres_table, backref='series')
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
    episodes = relation('TraktEpisode', backref='series', cascade='all, delete, delete-orphan')
    actors = relation('TraktActors', secondary=actors_table, backref='series')

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


class TraktSearchResult(Base):

    __tablename__ = 'trakt_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, nullable=False)
    series_id = Column(Integer, ForeignKey('trakt_series.tvdb_id'), nullable=True)
    series = relation(TraktSeries, backref='search_strings')


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
    def lookup_series(title=None, tvdb_id=None, only_cached=False, session=None):
        if not title and not tvdb_id:
            raise LookupError('No criteria specified for Trakt.tv Lookup')
        series = None

        def id_str():
            return '<name=%s, tvdb_id=%s>' % (title, tvdb_id)
        if tvdb_id:
            series = session.query(TraktSeries).filter(TraktSeries.tvdb_id == tvdb_id).first()
        if not series and title:
            series = session.query(TraktSeries).filter(func.lower(TraktSeries.title) == title.lower()).first()
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
                series = TraktSeries()
                series.tvdb_id = tvdb_id
                series.update(session=session)
                session.add(series)
            elif title:
                series_lookup = get_series_id(title)
                if series_lookup:
                    series = session.query(TraktSeries).filter(TraktSeries.tvdb_id == series_lookup).first()
                    if not series:
                        series = TraktSeries()
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
        episode = session.query(TraktEpisode).filter(TraktEpisode.series_id == series.tvdb_id).\
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
