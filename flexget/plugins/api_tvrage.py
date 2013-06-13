import tvrage.api
import logging
import datetime

from sqlalchemy import Column, Integer, DateTime, String, Index, Boolean, ForeignKey
from sqlalchemy.orm import relation

from flexget.utils.database import with_session
from flexget import db_schema


log = logging.getLogger('api_tvrage')
cache = {}    # we ll set episode in the cache to speed things up if multiple session ask for same show (now need to persist it ?)

"""
    See https://github.com/ckreutzer/python-tvrage for more details, it's pretty classic.
    A cache could be handy to avoid querying informations but I guess it should be implemented in
    python-tvrage itself.
"""
Base = db_schema.versioned_base('tvrage', 0)


class TVRageSeries(Base):
    __tablename__ = 'tvrage_series'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    episodes = relation('TVRageEpisodes', order_by='TVRageEpisodes.seasonnum, TVRageEpisodes.epnum', cascade='all, delete, delete-orphan')
    showid = Column(String)
    link = Column(String)
    classification = Column(String)
    genres = Column(String)
    country = Column(String)
    started = Column(Integer)
    ended = Column(Integer)
    seasons = Column(Integer)
    last_update = Column(DateTime)              # last time we updated the db for the show

    def __init__(self, series):
        # TODO init with tvrage object
        self.name = series.name.lower()
        self.showid = series.showid
        self.link = series.link
        self.classification = series.classification
        self.genres = ','.join(series.genres)
        self.country = series.country
        self.started = series.started
        self.ended = series.ended
        self.seasons = series.seasons
        self.last_update = datetime.datetime.now()

        for i in range(1, series.seasons+1):
            season = series.season(i)
            for j in season.keys():
                episode = TVRageEpisodes(season.episode(j))
                self.episodes.append(episode)

    @with_session
    def season(self, seasonnum, session=None):
        count = session.query(TVRageEpisodes).\
                    filter(TVRageEpisodes.tvrage_series_id == self.id).\
                    filter(TVRageEpisodes.seasonnum == seasonnum).\
                    count()
        if count == 0:
            return None
        res = TVRageSeason(self, seasonnum)
        return res

    def __str__(self):
        return '<TvrageSeries(title=%s,id=%s,last_update=%s)>' % (self.name, self.id, self.last_update)

    def finnished(self):
        return self.ended != 0

class TVRageSeason(object):
    def __init__(self,series,seasonnum):
        self.series = series
        self.seasonnum = seasonnum

    @with_session
    def episode(self, episodenum, session=None):
        res = session.query(TVRageEpisodes).\
            filter(TVRageEpisodes.tvrage_series_id == self.series.id).\
            filter(TVRageEpisodes.seasonnum == self.seasonnum).\
            filter(TVRageEpisodes.epnum == episodenum).first()
        return res


    def __str__(self):
        return '<TVRageSeason(title=%s,season=%s)>' % (self.series.name, self.seasonnum)

class TVRageEpisodes(Base):
    __tablename__ = 'tvrage_episode'
    id = Column(Integer, primary_key=True)
    tvrage_series_id = Column(Integer, ForeignKey('tvrage_series.id'), nullable=False)
    epnum = Column(Integer, index=True)
    seasonnum = Column(Integer, index=True)
    prodnum = Column(Integer)
    airdate = Column(DateTime)
    link = Column(String)
    title = Column(String)

    def __init__(self, ep):
        # TODO init with tvrage object
        self.epnum = ep.number
        self.seasonnum = ep.season
        self.prodnum = ep.prodnumber
        self.airdate = ep.airdate
        self.link = ep.link
        self.title = ep.title

    def __str__(self):
        return '<TVRageEpisodes(title=%s,id=%s,season=%s,episode=%s)>' % (self.title, self.id, self.seasonnum, self.epnum)

    """
        Returns the next episode from this episode
    """
    def next(self):
        res = session.query(TVRageEpisodes).\
            filter(TVRageEpisodes.tvrage_series_id == self.series.tvrage_series_id).\
            filter(TVRageEpisodes.seasonnum == self.seasonnum).\
            filter(TVRageEpisodes.epnum == episodenum+1).first()
        if res is not None:
            return res
        return session.query(TVRageEpisodes).\
            filter(TVRageEpisodes.tvrage_series_id == self.series.tvrage_series_id).\
            filter(TVRageEpisodes.seasonnum == self.seasonnum+1).\
            filter(TVRageEpisodes.epnum == 1).first()

@with_session
def lookup_series(name=None, session=None):
    # TODO : Maybe find a better way to find a match from a name, so far series are named in lowercase
    res = session.query(TVRageSeries).filter(TVRageSeries.name==name.lower()).first()
    # TODO : if too old result update
    if res is not None:
        return res
    fetched = tvrage.api.Show(name)
    series = TVRageSeries(fetched)
    session.add(series)
    return series
