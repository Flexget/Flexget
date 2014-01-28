from __future__ import unicode_literals, division, absolute_import
import logging
import datetime
import difflib
from socket import timeout

from sqlalchemy import Column, Integer, DateTime, String, Unicode, ForeignKey, select, update
from sqlalchemy.orm import relation
import tvrage.api

from flexget.event import event
from flexget.utils.database import with_session
from flexget import db_schema
from flexget.utils.database import pipe_list_synonym
from flexget.utils.sqlalchemy_utils import table_schema
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('api_tvrage')

Base = db_schema.versioned_base('tvrage', 2)
UPDATE_INTERVAL = '7 days'


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
    if ver == 1:
        raise db_schema.UpgradeImpossible
    return ver


class TVRageLookup(Base):
    __tablename__ = 'tvrage_lookup'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, index=True)
    failed_time = Column(DateTime)
    series_id = Column(Integer, ForeignKey('tvrage_series.id'))
    series = relation('TVRageSeries', uselist=False, cascade='all, delete')

    def __init__(self, name, series, **kwargs):
        super(TVRageLookup, self).__init__(**kwargs)
        self.name = name.lower()
        self.series = series


class TVRageSeries(Base):
    __tablename__ = 'tvrage_series'
    id = Column(Integer, primary_key=True)
    name = Column(String)
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
        self.update(series)

    def update(self, series):
        self.name = series.name
        self.showid = series.showid
        self.link = series.link
        self.classification = series.classification
        self.genres = [g for g in series.genres if g]  # Sometimes tvrage has a None in the genres list
        self.country = series.country
        self.started = series.started
        self.ended = series.ended
        self.seasons = series.seasons
        self.last_update = datetime.datetime.now()

        # Clear old eps before repopulating
        del self.episodes[:]
        for i in range(1, series.seasons + 1):
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
        self.update(ep)

    def update(self, ep):
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
    series = None
    res = session.query(TVRageLookup).filter(TVRageLookup.name == name.lower()).first()

    if res and not res.series:
        # The lookup failed in the past for this series, retry every week
        # TODO: 1.2 this should also retry with --retry or whatever flag imdb lookup is using for that
        if res.failed_time and res.failed_time > datetime.datetime.now() - datetime.timedelta(days=7):
            raise LookupError('Could not find show %s' % name)
    elif res:
        series = res.series
        # if too old result, clean the db and refresh it
        interval = parse_timedelta(UPDATE_INTERVAL)
        if datetime.datetime.now() > series.last_update + interval:
            log.debug('Refreshing tvrage info for %s', name)
        else:
            return series

    def store_failed_lookup():
        if res:
            res.series = None
            res.failed_time = datetime.datetime.now()
        else:
            session.add(TVRageLookup(name, None, failed_time=datetime.datetime.now()))
            session.commit()

    log.debug('Fetching tvrage info for %s' % name)
    try:
        fetched = tvrage.api.Show(name.encode('utf-8'))
    except tvrage.exceptions.ShowNotFound:
        store_failed_lookup()
        raise LookupError('Could not find show %s' % name)
    except (timeout, AttributeError):
        # AttributeError is due to a bug in tvrage package trying to access URLError.code
        raise LookupError('Timed out while connecting to tvrage')
    except TypeError:
        # TODO: There should be option to pass tvrage id directly from within series plugin via "set:" (like tvdb_id)
        # and search directly for tvrage id. This is problematic, because 3rd party TVRage API does not support this.
        raise LookupError('Returned invalid data for "%s". This is often caused when TVRage is missing episode info'
                          % name)
    # Make sure the result is close enough to the search
    if difflib.SequenceMatcher(a=name, b=fetched.name).ratio() < 0.7:
        log.debug('Show result `%s` was not a close enough match for `%s`' % (fetched.name, name))
        store_failed_lookup()
        raise LookupError('Could not find show %s' % name)
    if not series:
        series = session.query(TVRageSeries).filter(TVRageSeries.showid == fetched.showid).first()
    if not series:
        series = TVRageSeries(fetched)
        session.add(series)
        session.add(TVRageLookup(unicode(fetched.name), series))
    else:
        series.update(fetched)
    if name.lower() != fetched.name.lower():
        if res:
            res.series = series
        else:
            session.add(TVRageLookup(name, series))
    return series
