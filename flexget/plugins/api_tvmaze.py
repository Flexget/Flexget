from __future__ import unicode_literals, division, absolute_import

import logging
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, Numeric, PickleType
from sqlalchemy.orm import relation
from pytvmaze import get_show
from pytvmaze.exceptions import *

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.database import with_session

log = logging.getLogger('api_tvmaze')

DB_Version = 0
Base = db_schema.versioned_base('tvmaze', DB_Version)
UPDATE_INTERVAL = '7 days'

# TODO Genres table

class TVMazeLookup(Base):
    __tablename__ = 'tvmaze_lookup'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode, index=True)
    failed_time = Column(DateTime)
    series_id = Column(Integer, ForeignKey('tvmaze_series.id'))
    series = relation('TVMazeSeries', uselist=False, cascade='all, delete')

    def __init__(self, name, series, **kwargs):
        super(TVMazeLookup, self).__init__(**kwargs)
        self.name = name.lower()
        self.series = series


class TVMazeSeries(Base):
    __tablename__ = 'tvmaze_series'

    id = Column(Integer, primary_key=True)
    status = Column(Unicode)
    rating = Column(Numeric)
    genres = Column(String)
    weight = Column(Integer)
    updated = Column(DateTime)  # last time show was updated at tvmaze
    name = Column(String)
    language = Column(Unicode)
    schedule = Column(PickleType)
    url = Column(String)
    image = Column(PickleType)
    tvdb_id = Column(Integer)
    tvrage_id = Column(Integer)
    premiered = Column(DateTime)
    summary = Column(Unicode)
    _links = Column(PickleType)  # links to previous and next episode
    webChannel = Column(String)
    runtime = Column(Integer)
    type = Column(String)
    maze_id = Column(String)
    network = Column(Unicode)
    seasons = relation('TVMazeSeasons', order_by='TVMazeSeasons.number', cascade='all, delete, delete-orphan',
                       backref='series')
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series):
        self.update(series)

    def update(self, series):
        self.status = series.status
        self.rating = series.rating['average']
        self.genres = series.genres
        self.weight = series.weight
        self.updated = datetime.fromtimestamp(series.updated).strftime('%Y-%m-%d %H:%M:%S')
        self.name = series.name
        self.language = series.language
        self.schedule = series.scheduele
        self.url = series.url
        self.image = series.image
        self.tvdb_id = series.externals.get('thetvdb')
        self.tvrage_id = series.externals.get('tvrage')
        self.premiered = series.premiered
        self.summary = series.summary
        self._links = series._links
        self.webChannel = series.webChannel
        self.runtime = series.runtime
        self.type = series.type
        self.maze_id = series.maze_id
        self.network = series.network['name']
        self.last_update = datetime.now()

        del self.seasons[:]
        for season in series:
            season = TVMazeSeasons(season)
            self.seasons.append(season)

    def __repr__(self):
        return '<TVMazeSeries(title=%s,id=%s,last_update=%s)>' % (self.name, self.id, self.last_update)

    def __str__(self):
        return self.name


class TVMazeSeasons(Base):
    __tablename__ = 'tvmaze_season'

    id = Column(Integer, primary_key=True)
    tvmaze_series_id = Column(Integer, ForeignKey('tvmaze_series.id'), nullable=False)
    number = Column(Integer)
    episodes = relation('TVMazeEpisodes', order_by='TVMazeEpisodes.season', cascade='all, delete, delete-orphan',
                        backref='season')
    last_update = Column(DateTime)

    def __init__(self, season):
        self.update(season)

    def update(self, season):
        self.number = season.season_number
        self.last_update = datetime.now()

        del self.episodes[:]
        for episode in season:
            episode = TVMazeEpisodes(episode)
            self.episodes.append(episode)


class TVMazeEpisodes(Base):
    __tablename__ = 'tvmaze_epiosde'

    id = Column(Integer, primary_key=True)
    tvmaze_season_id = Column(Integer, ForeignKey('tvmaze_season.id'), nullable=False)
    name = Column(Unicode)
    airdate = Column(DateTime)
    url = Column(String)
    number = Column(Integer)
    season_number = Column(Integer)
    image = Column(String)
    airstamp = Column(DateTime)
    runtime = Column(Integer)
    maze_id = Column(Integer)
    last_update = Column(DateTime)

    def __init__(self, episode):
        self.update(episode)

    def update(self, episode):
        self.name = episode.name
        self.airdate = datetime.strptime(episode.airdate, '%Y-%m-%d')
        self.url = episode.url
        self.number = episode.episode_number
        self.season_number = episode.season_number
        self.image = episode.image
        self.airstamp = datetime.strptime(episode.airstamp, '%Y-%m-%dT%H:%M:%S%z')
        self.runtime = episode.runtime
        self.maze_id = episode.maze_id
        self.last_update = datetime.now()


class APITVMaze(object):

    @staticmethod
    @with_session
    def series_lookup(maze_id=None, tvdb_id=None, tvrage_id=None, title=None, session=None):
        if not any([maze_id, tvdb_id, tvrage_id, title]):
            raise LookupError('No parameters sent for TVMaze series lookup')
        show = None
        if maze_id:
            show = session.query(TVMazeSeries).filter(TVMazeSeries.maze_id == maze_id).first()
        elif tvdb_id:
            show = session.query(TVMazeSeries).filter(TVMazeSeries.tvdb_id == tvdb_id).first()
        elif tvrage_id:
            show = session.query(TVMazeSeries).filter(TVMazeSeries.tvrage_id == tvrage_id).first()
        if not show and title:
            show = session.query(TVMazeSeries).filter(TVMazeSeries.name == title.lower()).first()



@event('plugin.register')
def register_plugin():
    plugin.register(APITVMaze, 'api_tvmaze', api_ver=2)
