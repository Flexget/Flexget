import urllib2
import json
import requests
import logging
from flexget.utils import json
from flexget.utils.cached_input import cached
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry
import urllib
import re
from flexget.plugins.filter.series import normalize_series_name
from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

from flexget import schema
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema

'''
Flexget Dev API Key for Trakt.tv
6c228565a45a302e49fb7d2dab066c9ab948b7be
'''

api_key = '6c228565a45a302e49fb7d2dab066c9ab948b7be/'
search_show = 'http://api.trakt.tv/search/shows.json/'
episode_summary = 'http://api.trakt.tv/show/episode/summary.json/'
show_summary = 'http://api.trakt.tv/show/summary.json/'
Base = schema.versioned_base('api_trakt', 0)
log = logging.getLogger('api_trakt')

class TraktContainer(object):
#        """Base class for Trakt objects"""
    def __init__(self, init_dict=None):
        if isinstance(init_dict, dict):
            self.update_from_dict(init_dict)

    def update_from_dict(self, update_dict):
        """Populates any simple (string or number) attributes from a dict"""
        for col in self.__table__.columns:
            if isinstance(update_dict.get(col.name), (basestring, int, float)):
                setattr(self, col.name, update_dict[col.name])


class TraktEpisode(TraktContainer, Base):
    __tablename__ = "trakt_episodes"

    tvdb_id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(Unicode)
    season = Column(Integer)
    number = Column(Integer)
    overview = Column(Unicode)
    expired = Column(Boolean)

    series_id = Column(Integer, ForeignKey('trakt_series.id'), nullable=False)


class TraktSearchResult(Base):

    __tablename__ = 'trakt_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, nullable=False)
    series_id = Column(Integer, ForeignKey('trakt_series.id'), nullable=True)
    series = relation(Series, backref='search_strings')


class TraktSeries(TraktContainer, Base):
    __tablename__ = "trakt_series"

    tvdb_id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(Unicode)
    genres = relation('TraktGenre', secondary=genres_table, backref='')
    network = Column(Unicode, nullable=True)
    year = Column(Integer)
    certification = Column(Unicode) # TV-14 is unicode?
    overview = Column(Unicode)
    url = Column(Unicode) # url is unicode?

 #### still need to finish ####
    def update(self):
        if not self.tvdb_id:
            raise LookupError('Cannot update series without tvdb_id')
            url = show_summary + api_key + self.tvdb_id
            try:
                data = requests.get(url).json()
            except RequestException as e:
                raise LookupError('Request failed %s' % url)
            for value in data:
                if value['title']:
                    self.update_from_dict(data[value])
                else:
                    raise LookupError('Could not retrieve information from Trakt.')

    def __repr__(self):
        return '<Traktv Nmae=%s, TVDB_ID=%s>' % (self.series.title, self.series.tvdb_id)

@with_session
def lookup_series(title=None, tvdb_id=None, only_cached=False, session=None):
    if not name and not tvdb_id:
        raise LookupError('No criteria specified for Trakt.tv Lookup')
    log.debug('Lookup up trakt information for %r' % {'name': name, 'tvdb_id': tvdb_id})

    series = None
    def id_str():
        return '<name=%s, tvdb_id=%s>' % (name, tvdb_id)
    if tvdb_id:
        series = session.query(TraktSeries).filter(TraktSeries.tvdb_id == tvdb_id).first()
    if not series and title:
        series_filter = session.query(TraktSeries).filter(func.lower(TraktSeries.title) == title.lower())
        series = series_filter.first()
        if not series:
            found = session.query(TraktSearchResults). \
                filter(func.lower(TraktSearchResults.search) == title.lower()).first()
            if found and found.series:
                series = found.series

    if series:
        series.update()
        except LookupError as e:
            log.warning('Error while updating trakt, using cached data.' % e.message)
    else:
        if only_cached:
            raise LookupError('Series %s not found from cache' % id_str())
        try:
        log.debug('Series %s not found in cache, looking up from trakt.' % id_str())
        try:
            if tvdb_id:
                series = TraktSeries()
                series.tvdb_id = tvdb_id
                series.update()
                if series.seriesname:
                    session.add(series)
            elif title:
                tvdb_id = get_series_id(title)
                if tvdb_id:
                    series = session.query(TraktSeries).filter(TraktSeries.tvdb_id == tvdb_id).first()
                    if not series:
                        series = TraktSeries()
                        series.tvdb_id = tvdb_id
                        session.add(series)
                    if title.lower() != series.seriesname.lower():
                        session.add(TraktSearchResults(search=title, series=series))
        if not series:
            raise LookupError('No results found from traktv for %s' % id_str())
        if not series.seriesname:
            raise LookupError('Trakt result for series does not have a title')
        return series

@with_session
def lookup_episode(title=None, seasonnum=None, episodenum=None, tvdb_id=None, session=None, only_cached=False):
    series = lookup_series(title=title, tvdb_id=tvdb_id, only_cached=only_cached, session=session)
    if not series:
        raise LookupError('Could not identify series')
    if tvdb_id:
        ep_description = '%s.S%sE%s' % (series.title, seasonnum, episodenum)
        episode = session.query(TraktEpisode).filter(TraktEpisode.series_id) == series.tvdb_id).\
            filter(TraktEpisode.season == seasonnum).\
            filter(TraktEpisode.numer == episodenum).first()
        url = episode_summary + api_key + '%s/%s/%s' % (series.tvdb_id, seasonnum, episodenum)
    elif title:
        ep_description = '%s.S%sE%s' % (series.title, seasonnum, episodenum)
        episode = session.query(TraktEpisode).filter(TraktEpisode.series_id) == series.tvdb_id).\
            filter(TraktEpisode.season == seasonnum).\
            filter(TraktEpisode.numer == episodenum).first()
        url = episode_summary + api_key + '%s/%s/%s' % (series.title, seasonnum, episodenum)
    if episode:
        if episode.expired and not only_cached:
            log.info('Data for %r has expired, refreshing from tvdb' % episode)
            try:
                episode.update()
            except LookupError as e:
                log.warning('Error while updating from trakt (%s), using cached data.' % e.message)
        else:
            log.debug('Using episode info for %s from cache.' % ep_description)
    else:
        if only_cached:
            raise LookupError('Episode %s not found in cache' % ep_description)
        log.debug('Episode %s not found in cache, looking up from trakt.' % ep_description)
        try:
            data = reqests.get(url).json()
            if data:
                if 'status' in data:
                    raise LookupError('Error looking up episode')
                ep_data = data['episode']
                if ep_data:
                    episode = session.query(TraktEpisode).filter(TraktEpisode.id == ep_data.id.string).first()
                    if episode:
                        episode.update_from_dict(ep_data)
                    else:
                        episode = TraktEpisode(ep_data)
                    series.episodes.append(episode)
                    session.merge(series)
        except RequestException as e:
            raise LookupError('Error looking up episode from Trakt (%s)' % e)
        if episode:
            episode.series
            return episode
        else:
            raise LookupError('No results found for (%s)' % episode)

register_plugin(ApiTrakt, 'api_trakt')
