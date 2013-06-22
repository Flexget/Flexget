import tvrage.api  # See https://github.com/ckreutzer/python-tvrage for more details, it's pretty classic.
import logging
import datetime

from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, select, update
from sqlalchemy.orm import relation

from flexget.event import event
from flexget.utils.database import with_session
from flexget import db_schema
from flexget.utils.database import pipe_list_synonym
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('api_tvrage')

Base = db_schema.versioned_base('tvrage', 1)
update_interval = '7 days'


@event('manager.db_cleanup')
def db_cleanup(session):
    value = datetime.datetime.now() - parse_timedelta('30 days')
    for de in session.query(TVRageSeries).filter(TVRageSeries.last_update <= value).all():
        log.debug('deleting %s' % de)
        session.delete(de)


@db_schema.upgrade('tvrage')
def upgrade(ver, session):
    if ver == 0:
        series_table = table_schema('tvrage_series', session)
        for row in session.execute(select([series_table.c.id, series_table.c.genres])):
            # Recalculate the proper_count from title for old episodes
            new_genres = row['genres']
            if new_genres:
                new_genres = row['genres'].replace(',', '|')
            session.execute(update(series_table, series_table.c.id == row['id'], {'genres': new_genres}))
        ver = 1
    return ver


class TVRageSeries(Base):
    __tablename__ = 'tvrage_series'
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    episodes = relation('TVRageEpisodes', order_by='TVRageEpisodes.season, TVRageEpisodes.episode',
                        cascade='all, delete, delete-orphan')
    showid = Column(String)
    link = Column(String)
    classification = Column(String)
    _genres = Column('genres', String)
    genres = pipe_list_synonym('_genres')
    country = Column(String)
    started = Column(Integer)
    ended = Column(Integer)
    seasons = Column(Integer)
    last_update = Column(DateTime)  # last time we updated the db for the show

    def __init__(self, series):
        self.name = series.name.lower()
        self.showid = series.showid
        self.link = series.link
        self.classification = series.classification
        self.genres = filter(None, series.genres)  # Sometimes tvdb has a None in the genres list
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
    def find_episode(self, season, episode, session=None):
        return (session.query(TVRageEpisodes).
                filter(TVRageEpisodes.tvrage_series_id == self.id).
                filter(TVRageEpisodes.season == season).
                filter(TVRageEpisodes.episode == episode).first())

    def __str__(self):
        return '<TvrageSeries(title=%s,id=%s,last_update=%s)>' % (self.name, self.id, self.last_update)

    def finished(self):
        return self.ended != 0


class TVRageEpisodes(Base):
    __tablename__ = 'tvrage_episode'
    id = Column(Integer, primary_key=True)
    tvrage_series_id = Column(Integer, ForeignKey('tvrage_series.id'), nullable=False)
    episode = Column(Integer, index=True)
    season = Column(Integer, index=True)
    prodnum = Column(Integer)
    airdate = Column(DateTime)
    link = Column(String)
    title = Column(String)

    def __init__(self, ep):
        self.episode = ep.number
        self.season = ep.season
        self.prodnum = ep.prodnumber
        self.airdate = ep.airdate
        self.link = ep.link
        self.title = ep.title

    def __str__(self):
        return '<TVRageEpisodes(title=%s,id=%s,season=%s,episode=%s)>' % (self.title, self.id, self.season, self.episode)

    @with_session
    def next(self, session=None):
        """Returns the next episode after this episode"""
        res = session.query(TVRageEpisodes).\
            filter(TVRageEpisodes.tvrage_series_id == self.tvrage_series_id).\
            filter(TVRageEpisodes.season == self.season).\
            filter(TVRageEpisodes.episode == self.episode+1).first()
        if res is not None:
            return res
        return session.query(TVRageEpisodes).\
            filter(TVRageEpisodes.tvrage_series_id == self.tvrage_series_id).\
            filter(TVRageEpisodes.season == self.season+1).\
            filter(TVRageEpisodes.episode == 1).first()


@with_session
def lookup_series(name=None, session=None):
    # TODO : Maybe find a better way to find a match from a name, so far series are named in lowercase
    res = session.query(TVRageSeries).filter(TVRageSeries.name == name.lower()).first()

    if res is not None:
        # if too old result, clean the db and refresh it
        interval = parse_timedelta(update_interval)
        if datetime.datetime.now() > res.last_update+interval:
            log.info('Refreshing tvrage info for %s' % name)
            session.delete(res)
        else:
            return res
    log.info('Fetching tvrage info for %s' % name)
    try:
        fetched = tvrage.api.Show(name)
    except tvrage.exceptions.ShowNotFound:
        raise LookupError('Could not find show %s' % name)
    series = TVRageSeries(fetched)
    session.add(series)
    return series
