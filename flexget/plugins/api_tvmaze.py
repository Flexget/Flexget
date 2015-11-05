from __future__ import unicode_literals, division, absolute_import
import logging
import datetime
import difflib
from socket import timeout
from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, select, update, func
from sqlalchemy.orm import relation
import tvrage.api
import tvrage.feeds
from tvrage.util import TvrageError
from flexget.event import event
from flexget.utils.database import with_session
from flexget import db_schema
from flexget.utils.database import pipe_list_synonym
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('api_tvmaze')

Base = db_schema.versioned_base('tvmaze', 0)
UPDATE_INTERVAL = '7 days'


# TODO genres table?
# todo convert 'updated' to time stamp
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
    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String)
    episodes = relation('TVMazeEpisodes', order_by='TVMazeEpisodes.season, TVMazeEpisodes.episode',
                        cascade='all, delete, delete-orphan')
    mazeid = Column(String)
    rating = Column(String)
    genres = Column(String)
    weight = Column(Integer)
    seasons = relation('TVMazeSeasons', order_by='TVMazeSeasons.number', cascade='all, delete, delete-orphan',
                       backref='show')
    updated = Column(DateTime)  # last time show was updated at tvmaze
    language = Column(Unicode)
    schedule = Column(String)
    url = Column(String)
    image = Column(String)
    tvdbID = Column(Integer)
    tvrageID = Column(Integer)
    premiered = Column(DateTime)
    summary = Column(Unicode)
    previous_episode = relation('TVMazeEpisode', backref='show')
    next_episode = relation('TVMazeEpisode', backref='show')
    webChannel = Column(String)
    runtime = Column(Integer)
    type = Column(String)
    network = Column(Unicode)
    last_update = Column(DateTime)  # last time we updated the db for the show
