from __future__ import unicode_literals, division, absolute_import

import datetime
import logging

from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, Numeric, PickleType
from sqlalchemy.orm import relation

from flexget import db_schema

log = logging.getLogger('api_tvmaze')

DB_Version = 0
Base = db_schema.versioned_base('tvmaze', DB_Version)
UPDATE_INTERVAL = '7 days'


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
    externals = Column(PickleType)  # Dict to tvdb & tvrage IDs
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
        self.updated = datetime.datetime.fromtimestamp(series.updated).strftime('%Y-%m-%d %H:%M:%S')
        self.name = series.name
        self.language = series.language
        self.schedule = series.scheduele
        self.url = series.url
        self.image = series.image
        self.externals = series.externals
        self.premiered = series.premiered
        self.summary = series.summary
        self._links = series._links
        self.webChannel = series.webChannel
        self.runtime = series.runtime
        self.type = series.type
        self.maze_id = series.maze_id
        self.network = series.network['name']
        self.last_update = datetime.datetime.now()

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
        self.last_update = datetime.datetime.now()


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
        self.airdate = datetime.datetime.strptime(episode.airdate, '%Y-%m-%d')
        self.url = episode.url
        self.number = episode.episode_number
        self.season_number = episode.season_number
        self.image = episode.image
        self.airstamp = datetime.datetime.strptime(episode.airstamp, '%Y-%m-%dT%H:%M:%S%z')
        self.runtime = episode.runtime
        self.maze_id = episode.maze_id
        self.last_update = datetime.datetime.now()


