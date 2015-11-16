from __future__ import unicode_literals, division, absolute_import

import logging

import datetime
from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, Numeric, PickleType
from sqlalchemy.orm import relation

from flexget import db_schema

log = logging.getLogger('api_tvmaze')

DB_Version = 0
Base = db_schema.versioned_base('tvmaze', DB_Version)
UPDATE_INTERVAL = '7 days'


# TODO genres table?
# todo convert 'updated' to time stamp from epoch
# todo when to use unicode and wehn to use string



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
    externals = Column(PickleType) # Dict to tvdb & tvrage IDs
    premiered = Column(DateTime)
    summary = Column(Unicode)
    _links = Column(PickleType) # links to previous and next episode
    webChannel = Column(String)
    runtime = Column(Integer)
    type = Column(String)
    maze_id = Column(String)
    network = Column(Unicode)
    seasons = relation('TVMazeSeasons', order_by='TVMazeSeasons.number', cascade='all, delete, delete-orphan',
                       backref='show')
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series):
        self.update(series)

    def update(self, series):
        self.status = series.status
        self.rating =series.rating['average']
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
    episodes = relation('TVMazeEpisodes', order_by='TVMazeEpisodes.season, TVMazeEpisodes.episode',
                        cascade='all, delete, delete-orphan')
    last_update = Column(DateTime)

    def __init__(self, season):
        self.update(season)

    def update(self, season):
        self.number = season.season_number

class TVMazeEpisodes(Base):
    __tablename__ = 'tvmaze_epiosde'
    id = Column(Integer, primary_key=True)
