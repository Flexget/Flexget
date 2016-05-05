from __future__ import unicode_literals, division, absolute_import

import argparse
import logging
import re
import time
from copy import copy
from datetime import datetime, timedelta

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring
from sqlalchemy import (Column, Integer, String, Unicode, DateTime, Boolean,
                        desc, select, update, delete, ForeignKey, Index, func, and_, not_)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import relation, backref, object_session

from flexget import db_schema, options, plugin
from flexget.config_schema import one_or_more
from flexget.event import event, fire_event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.plugins.parsers import SERIES_ID_TYPES
from flexget.utils import qualities
from flexget.utils.database import quality_property, with_session
from flexget.utils.log import log_once
from flexget.utils.sqlalchemy_utils import (table_columns, table_exists, drop_tables, table_schema, table_add_column,
                                            create_index)
from flexget.utils.tools import merge_dict_from_to, parse_timedelta

SCHEMA_VER = 12

log = logging.getLogger('series')
Base = db_schema.versioned_base('series', SCHEMA_VER)


@db_schema.upgrade('series')
def upgrade(ver, session):
    if ver is None:
        if table_exists('episode_qualities', session):
            log.info('Series database format is too old to upgrade, dropping and recreating tables.')
            # Drop the deprecated data
            drop_tables(['series', 'series_episodes', 'episode_qualities'], session)
            # Create new tables from the current models
            Base.metadata.create_all(bind=session.bind)
        # Upgrade episode_releases table to have a proper count and seed it with appropriate numbers
        columns = table_columns('episode_releases', session)
        if 'proper_count' not in columns:
            log.info('Upgrading episode_releases table to have proper_count column')
            table_add_column('episode_releases', 'proper_count', Integer, session)
            release_table = table_schema('episode_releases', session)
            for row in session.execute(select([release_table.c.id, release_table.c.title])):
                # Recalculate the proper_count from title for old episodes
                proper_count = get_plugin_by_name('parsing').parse_series(row['title']).proper_count
                session.execute(update(release_table, release_table.c.id == row['id'], {'proper_count': proper_count}))
        ver = 0
    if ver == 0:
        log.info('Migrating first_seen column from series_episodes to episode_releases table.')
        # Create the column in episode_releases
        table_add_column('episode_releases', 'first_seen', DateTime, session)
        # Seed the first_seen value for all the past releases with the first_seen of their episode.
        episode_table = table_schema('series_episodes', session)
        release_table = table_schema('episode_releases', session)
        for row in session.execute(select([episode_table.c.id, episode_table.c.first_seen])):
            session.execute(update(release_table, release_table.c.episode_id == row['id'],
                                   {'first_seen': row['first_seen']}))
        ver = 1
    if ver == 1:
        log.info('Adding `identified_by` column to series table.')
        table_add_column('series', 'identified_by', String, session)
        ver = 2
    if ver == 2:
        log.info('Creating index on episode_releases table.')
        create_index('episode_releases', session, 'episode_id')
        ver = 3
    if ver == 3:
        # Remove index on Series.name
        try:
            Index('ix_series_name').drop(bind=session.bind)
        except OperationalError:
            log.debug('There was no ix_series_name index to remove.')
        # Add Series.name_lower column
        log.info('Adding `name_lower` column to series table.')
        table_add_column('series', 'name_lower', Unicode, session)
        series_table = table_schema('series', session)
        create_index('series', session, 'name_lower')
        # Fill in lower case name column
        session.execute(update(series_table, values={'name_lower': func.lower(series_table.c.name)}))
        ver = 4
    if ver == 4:
        log.info('Adding `identified_by` column to episodes table.')
        table_add_column('series_episodes', 'identified_by', String, session)
        series_table = table_schema('series', session)
        # Clear out identified_by id series so that they can be auto detected again
        session.execute(update(series_table, series_table.c.identified_by != 'ep', {'identified_by': None}))
        # Warn users about a possible config change needed.
        log.warning('If you are using `identified_by: id` option for the series plugin for date, '
                    'or abolute numbered series, you will need to update your config. Two new identified_by modes have '
                    'been added, `date` and `sequence`. In addition, if you are using auto identified_by, it will'
                    'be relearned based on upcoming episodes.')
        ver = 5
    if ver == 5:
        # Episode advancement now relies on identified_by being filled for the episodes.
        # This action retroactively marks 'ep' mode for all episodes where the series is already in 'ep' mode.
        series_table = table_schema('series', session)
        ep_table = table_schema('series_episodes', session)
        ep_mode_series = select([series_table.c.id], series_table.c.identified_by == 'ep')
        where_clause = and_(ep_table.c.series_id.in_(ep_mode_series),
                            ep_table.c.season != None, ep_table.c.number != None, ep_table.c.identified_by == None)
        session.execute(update(ep_table, where_clause, {'identified_by': 'ep'}))
        ver = 6
    if ver == 6:
        # Translate old qualities into new quality requirements
        release_table = table_schema('episode_releases', session)
        for row in session.execute(select([release_table.c.id, release_table.c.quality])):
            # Webdl quality no longer has dash
            new_qual = row['quality'].replace('web-dl', 'webdl')
            if row['quality'] != new_qual:
                session.execute(update(release_table, release_table.c.id == row['id'],
                                       {'quality': new_qual}))
        ver = 7
    # Normalization rules changed for 7 and 8, but only run this once
    if ver in [7, 8]:
        # Merge series that qualify as duplicates with new normalization scheme
        series_table = table_schema('series', session)
        ep_table = table_schema('series_episodes', session)
        all_series = session.execute(select([series_table.c.name, series_table.c.id]))
        unique_series = {}
        for row in all_series:
            unique_series.setdefault(normalize_series_name(row['name']), []).append(row['id'])
        for series, ids in unique_series.items():
            session.execute(update(ep_table, ep_table.c.series_id.in_(ids), {'series_id': ids[0]}))
            if len(ids) > 1:
                session.execute(delete(series_table, series_table.c.id.in_(ids[1:])))
            session.execute(update(series_table, series_table.c.id == ids[0], {'name_lower': series}))
        ver = 9
    if ver == 9:
        table_add_column('series', 'begin_episode_id', Integer, session)
        ver = 10
    if ver == 10:
        # Due to bad db cleanups there may be invalid entries in series_tasks table
        series_tasks = table_schema('series_tasks', session)
        series_table = table_schema('series', session)
        log.verbose('Repairing series_tasks table data')
        session.execute(delete(series_tasks, ~series_tasks.c.series_id.in_(select([series_table.c.id]))))
        ver = 11
    if ver == 11:
        # SeriesTasks was cleared out due to a bug, make sure they get recalculated next run #2772
        from flexget.task import config_changed
        config_changed(session=session)
        ver = 12

    return ver


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Clean up old undownloaded releases
    result = session.query(Release). \
        filter(Release.downloaded == False). \
        filter(Release.first_seen < datetime.now() - timedelta(days=120)).delete(False)
    if result:
        log.verbose('Removed %d undownloaded episode releases.', result)
    # Clean up episodes without releases
    result = session.query(Episode).filter(~Episode.releases.any()).filter(~Episode.begins_series.any()).delete(False)
    if result:
        log.verbose('Removed %d episodes without releases.', result)
    # Clean up series without episodes that aren't in any tasks
    result = session.query(Series).filter(~Series.episodes.any()).filter(~Series.in_tasks.any()).delete(False)
    if result:
        log.verbose('Removed %d series without episodes.', result)


@event('manager.lock_acquired')
def repair(manager):
    # Perform database repairing and upgrading at startup.
    if not manager.persist.get('series_repaired', False):
        session = Session()
        try:
            # For some reason at least I have some releases in database which don't belong to any episode.
            for release in session.query(Release).filter(Release.episode == None).all():
                log.info('Purging orphan release %s from database', release.title)
                session.delete(release)
            session.commit()
        finally:
            session.close()
        manager.persist['series_repaired'] = True

    # Run clean_series the first time we get a database lock, since we won't have had one the first time the config
    # got loaded.
    clean_series(manager)


@event('manager.config_updated')
def clean_series(manager):
    # Unmark series from tasks which have been deleted.
    if not manager.has_lock:
        return
    with Session() as session:
        removed_tasks = session.query(SeriesTask)
        if manager.tasks:
            removed_tasks = removed_tasks.filter(not_(SeriesTask.name.in_(manager.tasks)))
        deleted = removed_tasks.delete(synchronize_session=False)
        if deleted:
            session.commit()


TRANSLATE_MAP = {ord(u'&'): u' and '}
for char in u'\'\\':
    TRANSLATE_MAP[ord(char)] = u''
for char in u'_./-,[]():':
    TRANSLATE_MAP[ord(char)] = u' '


def normalize_series_name(name):
    """Returns a normalized version of the series name."""
    name = name.lower()
    name = name.replace('&amp;', ' and ')
    name = name.translate(TRANSLATE_MAP)  # Replaced some symbols with spaces
    name = u' '.join(name.split())
    return name


class NormalizedComparator(Comparator):
    def operate(self, op, other):
        return op(self.__clause_element__(), normalize_series_name(other))


class AlternateNames(Base):
    """ Similar to Series. Name is handled case insensitively transparently.
    """

    __tablename__ = 'series_alternate_names'
    id = Column(Integer, primary_key=True)
    _alt_name = Column('alt_name', Unicode)
    _alt_name_normalized = Column('alt_name_normalized', Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)

    def name_setter(self, value):
        self._alt_name = value
        self._alt_name_normalized = normalize_series_name(value)

    def name_getter(self):
        return self._alt_name

    def name_comparator(self):
        return NormalizedComparator(self._alt_name_normalized)

    alt_name = hybrid_property(name_getter, name_setter)
    alt_name.comparator(name_comparator)

    def __init__(self, name):
        self.alt_name = name

    def __str__(self):
        return '<SeriesAlternateName(series_id=%s, alt_name=%s)>' % (self.series_id, self.alt_name)

    def __repr__(self):
        return str(self).encode('ascii', 'replace')


class Series(Base):
    """ Name is handled case insensitively transparently
    """

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    _name = Column('name', Unicode)
    _name_normalized = Column('name_lower', Unicode, index=True, unique=True)
    identified_by = Column(String)
    begin_episode_id = Column(Integer, ForeignKey('series_episodes.id', name='begin_episode_id', use_alter=True))
    begin = relation('Episode', uselist=False, primaryjoin="Series.begin_episode_id == Episode.id",
                     foreign_keys=[begin_episode_id], post_update=True, backref='begins_series')
    episodes = relation('Episode', backref='series', cascade='all, delete, delete-orphan',
                        primaryjoin='Series.id == Episode.series_id')
    in_tasks = relation('SeriesTask', backref=backref('series', uselist=False), cascade='all, delete, delete-orphan')
    alternate_names = relation('AlternateNames', backref='series', cascade='all, delete, delete-orphan')

    # Make a special property that does indexed case insensitive lookups on name, but stores/returns specified case
    def name_getter(self):
        return self._name

    def name_setter(self, value):
        self._name = value
        self._name_normalized = normalize_series_name(value)

    def name_comparator(self):
        return NormalizedComparator(self._name_normalized)

    name = hybrid_property(name_getter, name_setter)
    name.comparator(name_comparator)

    def __str__(self):
        return '<Series(id=%s,name=%s)>' % (self.id, self.name)

    def __repr__(self):
        return str(self).encode('ascii', 'replace')


class Episode(Base):
    __tablename__ = 'series_episodes'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)

    season = Column(Integer)
    number = Column(Integer)

    identified_by = Column(String)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    releases = relation('Release', backref='episode', cascade='all, delete, delete-orphan')

    @hybrid_property
    def first_seen(self):
        if not self.releases:
            return None
        return min(release.first_seen for release in self.releases)

    @first_seen.expression
    def first_seen(cls):
        return select([func.min(Release.first_seen)]).where(Release.episode_id == cls.id). \
            correlate(Episode.__table__).label('first_seen')

    @property
    def age(self):
        """
        :return: Pretty string representing age of episode. eg "23d 12h" or "No releases seen"
        """
        if not self.first_seen:
            return 'No releases seen'
        diff = datetime.now() - self.first_seen
        age_days = diff.days
        age_hours = diff.seconds // 60 // 60
        age = ''
        if age_days:
            age += '%sd ' % age_days
        age += '%sh' % age_hours
        return age

    @property
    def is_premiere(self):
        if self.season == 1 and self.number in (0, 1):
            return 'Series Premiere'
        elif self.number in (0, 1):
            return 'Season Premiere'
        return False

    @property
    def downloaded_releases(self):
        return [release for release in self.releases if release.downloaded]

    def __str__(self):
        return '<Episode(id=%s,identifier=%s,season=%s,number=%s)>' % \
               (self.id, self.identifier, self.season, self.number)

    def __repr__(self):
        return str(self).encode('ascii', 'replace')

    def __eq__(self, other):
        if not isinstance(other, Episode):
            return NotImplemented
        if self.identified_by != other.identified_by:
            return NotImplemented
        return self.identifier == other.identifier

    def __lt__(self, other):
        if not isinstance(other, Episode):
            return NotImplemented
        if self.identified_by != other.identified_by:
            return NotImplemented
        if self.identified_by in ['ep', 'sequence']:
            return self.season < other.season or (self.season == other.season and self.number < other.number)
        if self.identified_by == 'date':
            return self.identifier < other.identifier
        # Can't compare id type identifiers
        return NotImplemented

    def __hash__(self):
        return self.id


Index('episode_series_identifier', Episode.series_id, Episode.identifier)


class Release(Base):
    __tablename__ = 'episode_releases'

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'), nullable=False, index=True)
    _quality = Column('quality', String)
    quality = quality_property('_quality')
    downloaded = Column(Boolean, default=False)
    proper_count = Column(Integer, default=0)
    title = Column(Unicode)
    first_seen = Column(DateTime)

    def __init__(self):
        self.first_seen = datetime.now()

    @property
    def proper(self):
        # TODO: TEMP
        import warnings
        warnings.warn("accessing deprecated release.proper, use release.proper_count instead")
        return self.proper_count > 0

    def __str__(self):
        return '<Release(id=%s,quality=%s,downloaded=%s,proper_count=%s,title=%s)>' % \
               (self.id, self.quality, self.downloaded, self.proper_count, self.title)

    def __repr__(self):
        return str(self).encode('ascii', 'replace')


class SeriesTask(Base):
    __tablename__ = 'series_tasks'

    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    name = Column(Unicode, index=True)

    def __init__(self, name):
        self.name = name


def get_latest_status(episode):
    """
    :param episode: Instance of Episode
    :return: Status string for given episode
    """
    status = ''
    for release in sorted(episode.releases, key=lambda r: r.quality):
        if not release.downloaded:
            continue
        status += release.quality.name
        if release.proper_count > 0:
            status += '-proper'
            if release.proper_count > 1:
                status += str(release.proper_count)
        status += ', '
    return status.rstrip(', ') if status else None


@with_session
def get_series_summary(configured=None, premieres=None, status=None, days=None, start=None, stop=None, count=False,
                       sort_by='show_name', descending=None, session=None):
    """
    Return a query with results for all series.
    :param configured: 'configured' for shows in config, 'unconfigured' for shows not in config, 'all' for both.
    Default is 'all'
    :param premieres: Return only shows with 1 season and less than 3 episodes
    :param status: Stale or not
    :param days: Value to determine stale
    :param page_size: Number of result per page
    :param page: Page number to return
    :param count: Decides whether to return count of all shows or data itself
     :param session: Passed session
    :return:
    """
    if not configured:
        configured = 'configured'
    elif configured not in ['configured', 'unconfigured', 'all']:
        raise LookupError('"configured" parameter must be either "configured", "unconfigured", or "all"')
    query = session.query(Series)
    query = query.outerjoin(Series.episodes).outerjoin(Episode.releases).outerjoin(Series.in_tasks).group_by(Series.id)
    if configured == 'configured':
        query = query.having(func.count(SeriesTask.id) >= 1)
    elif configured == 'unconfigured':
        query = query.having(func.count(SeriesTask.id) < 1)
    if premieres:
        query = (query.having(func.max(Episode.season) <= 1).having(func.max(Episode.number) <= 2).
                 having(func.count(SeriesTask.id) < 1)).filter(Release.downloaded == True)
    if status == 'new':
        if not days:
            days = 7
        query = query.having(func.max(Episode.first_seen) > datetime.now() - timedelta(days=days))
    if status == 'stale':
        if not days:
            days = 365
        query = query.having(func.max(Episode.first_seen) < datetime.now() - timedelta(days=days))
    if count:
        return query.count()
    if sort_by == 'show_name':
        order_by = Series.name
    elif sort_by == 'last_download_date':
        order_by = func.max(Release.first_seen)
    query = query.order_by(desc(order_by)) if descending else query.order_by(order_by)
    query = query.slice(start, stop).from_self()
    return query


def get_latest_episode(series):
    """Return latest known identifier in dict (season, episode, name) for series name"""
    session = Session.object_session(series)
    episode = session.query(Episode).join(Episode.series). \
        filter(Series.id == series.id). \
        filter(Episode.season != None). \
        order_by(desc(Episode.season)). \
        order_by(desc(Episode.number)).first()
    if not episode:
        # log.trace('get_latest_info: no info available for %s', name)
        return False
    # log.trace('get_latest_info, series: %s season: %s episode: %s' % \
    #    (name, episode.season, episode.number))
    return episode


def auto_identified_by(series):
    """
    Determine if series `name` should be considered identified by episode or id format

    Returns 'ep', 'sequence', 'date' or 'id' if enough history is present to identify the series' id type.
    Returns 'auto' if there is not enough history to determine the format yet
    """

    session = Session.object_session(series)
    type_totals = dict(session.query(Episode.identified_by, func.count(Episode.identified_by)).join(Episode.series).
                       filter(Series.id == series.id).group_by(Episode.identified_by).all())
    # Remove None and specials from the dict,
    # we are only considering episodes that we know the type of (parsed with new parser)
    type_totals.pop(None, None)
    type_totals.pop('special', None)
    if not type_totals:
        return 'auto'
    log.debug('%s episode type totals: %r', series.name, type_totals)
    # Find total number of parsed episodes
    total = sum(type_totals.values())
    # See which type has the most
    best = max(type_totals, key=lambda x: type_totals[x])

    # Ep mode locks in faster than the rest. At 2 seen episodes.
    if type_totals.get('ep', 0) >= 2 and type_totals['ep'] > total / 3:
        log.info('identified_by has locked in to type `ep` for %s', series.name)
        return 'ep'
    # If we have over 3 episodes all of the same type, lock in
    if len(type_totals) == 1 and total >= 3:
        return best
    # Otherwise wait until 5 episodes to lock in
    if total >= 5:
        log.info('identified_by has locked in to type `%s` for %s', best, series.name)
        return best
    log.verbose('identified by is currently on `auto` for %s. '
                'Multiple id types may be accepted until it locks in on the appropriate type.', series.name)
    return 'auto'


def get_latest_release(series, downloaded=True, season=None):
    """
    :param Series series: SQLAlchemy session
    :param Downloaded: find only downloaded releases
    :param Season: season to find newest release for
    :return: Instance of Episode or None if not found.
    """
    session = Session.object_session(series)
    releases = session.query(Episode).join(Episode.releases, Episode.series).filter(Series.id == series.id)

    if downloaded:
        releases = releases.filter(Release.downloaded == True)

    if season is not None:
        releases = releases.filter(Episode.season == season)

    if series.identified_by and series.identified_by != 'auto':
        releases = releases.filter(Episode.identified_by == series.identified_by)

    if series.identified_by in ['ep', 'sequence']:
        latest_release = releases.order_by(desc(Episode.season), desc(Episode.number)).first()
    elif series.identified_by == 'date':
        latest_release = releases.order_by(desc(Episode.identifier)).first()
    else:
        # We have to label the order_by clause to disambiguate from Release.first_seen #3055
        latest_release = releases.order_by(desc(Episode.first_seen.label('ep_first_seen'))).first()

    if not latest_release:
        log.debug('get_latest_release returning None, no downloaded episodes found for: %s', series.name)
        return

    return latest_release


def new_eps_after(since_ep):
    """
    :param since_ep: Episode instance
    :return: Number of episodes since then
    """
    session = Session.object_session(since_ep)
    series = since_ep.series
    series_eps = session.query(Episode).join(Episode.series). \
        filter(Series.id == series.id)
    if series.identified_by == 'ep':
        if since_ep.season is None or since_ep.number is None:
            log.debug('new_eps_after for %s falling back to timestamp because latest dl in non-ep format' %
                      series.name)
            return series_eps.filter(Episode.first_seen > since_ep.first_seen).count()
        return series_eps.filter((Episode.identified_by == 'ep') &
                                 (((Episode.season == since_ep.season) & (Episode.number > since_ep.number)) |
                                  (Episode.season > since_ep.season))).count()
    elif series.identified_by == 'seq':
        return series_eps.filter(Episode.number > since_ep.number).count()
    elif series.identified_by == 'id':
        return series_eps.filter(Episode.first_seen > since_ep.first_seen).count()
    else:
        log.debug('unsupported identified_by %s', series.identified_by)
        return 0


def store_parser(session, parser, series=None, quality=None):
    """
    Push series information into database. Returns added/existing release.

    :param session: Database session to use
    :param parser: parser for release that should be added to database
    :param series: Series in database to add release to. Will be looked up if not provided.
    :param quality: If supplied, this will override the quality from the series parser
    :return: List of Releases
    """
    if quality is None:
        quality = parser.quality
    if not series:
        # if series does not exist in database, add new
        series = session.query(Series). \
            filter(Series.name == parser.name). \
            filter(Series.id != None).first()
        if not series:
            log.debug('adding series %s into db', parser.name)
            series = Series()
            series.name = parser.name
            session.add(series)
            log.debug('-> added %s' % series)

    releases = []
    for ix, identifier in enumerate(parser.identifiers):
        # if episode does not exist in series, add new
        episode = session.query(Episode).filter(Episode.series_id == series.id). \
            filter(Episode.identifier == identifier). \
            filter(Episode.series_id != None).first()
        if not episode:
            log.debug('adding episode %s into series %s', identifier, parser.name)
            episode = Episode()
            episode.identifier = identifier
            episode.identified_by = parser.id_type
            # if episodic format
            if parser.id_type == 'ep':
                episode.season = parser.season
                episode.number = parser.episode + ix
            elif parser.id_type == 'sequence':
                episode.season = 0
                episode.number = parser.id + ix
            series.episodes.append(episode)  # pylint:disable=E1103
            log.debug('-> added %s' % episode)

        # if release does not exists in episode, add new
        #
        # NOTE:
        #
        # filter(Release.episode_id != None) fixes weird bug where release had/has been added
        # to database but doesn't have episode_id, this causes all kinds of havoc with the plugin.
        # perhaps a bug in sqlalchemy?
        release = session.query(Release).filter(Release.episode_id == episode.id). \
            filter(Release.title == parser.data). \
            filter(Release.quality == quality). \
            filter(Release.proper_count == parser.proper_count). \
            filter(Release.episode_id != None).first()
        if not release:
            log.debug('adding release %s into episode', parser)
            release = Release()
            release.quality = quality
            release.proper_count = parser.proper_count
            release.title = parser.data
            episode.releases.append(release)  # pylint:disable=E1103
            log.debug('-> added %s' % release)
        releases.append(release)
    session.flush()  # Make sure autonumber ids are populated
    return releases


def set_series_begin(series, ep_id):
    """
    Set beginning for series

    :param Series series: Series instance
    :param ep_id: Integer for sequence mode, SxxEyy for episodic and yyyy-mm-dd for date.
    :raises ValueError: If malformed ep_id or series in different mode
    """
    # If identified_by is not explicitly specified, auto-detect it based on begin identifier
    # TODO: use some method of series parser to do the identifier parsing
    session = Session.object_session(series)
    if isinstance(ep_id, int):
        identified_by = 'sequence'
    elif re.match(r'(?i)^S\d{1,4}E\d{1,3}$', ep_id):
        identified_by = 'ep'
        ep_id = ep_id.upper()
    elif re.match(r'\d{4}-\d{2}-\d{2}', ep_id):
        identified_by = 'date'
    else:
        # Check if a sequence identifier was passed as a string
        try:
            ep_id = int(ep_id)
            identified_by = 'sequence'
        except ValueError:
            raise ValueError('`%s` is not a valid episode identifier' % ep_id)
    if series.identified_by not in ['auto', '', None]:
        if identified_by != series.identified_by:
            raise ValueError('`begin` value `%s` does not match identifier type for identified_by `%s`' %
                             (ep_id, series.identified_by))
    series.identified_by = identified_by
    episode = (session.query(Episode).filter(Episode.series_id == series.id).
               filter(Episode.identified_by == series.identified_by).
               filter(Episode.identifier == str(ep_id)).first())
    if not episode:
        # TODO: Don't duplicate code from self.store method
        episode = Episode()
        episode.identifier = ep_id
        episode.identified_by = identified_by
        if identified_by == 'ep':
            match = re.match(r'S(\d+)E(\d+)', ep_id)
            episode.season = int(match.group(1))
            episode.number = int(match.group(2))
        elif identified_by == 'sequence':
            episode.season = 0
            episode.number = ep_id
        series.episodes.append(episode)
        # Need to flush to get an id on new Episode before assigning it as series begin
        session.flush()
    series.begin = episode


def remove_series(name, forget=False):
    """
    Remove a whole series `name` from database.
    :param name: Name of series to be removed
    :param forget: Indication whether or not to fire a 'forget' event
    """
    downloaded_releases = []
    with Session() as session:
        series = session.query(Series).filter(Series.name == name).all()
        if series:
            for s in series:
                if forget:
                    for episode in s.episodes:
                        downloaded_releases = [release.title for release in episode.downloaded_releases]
                session.delete(s)
            session.commit()
            log.debug('Removed series %s from database.', name)
        else:
            raise ValueError('Unknown series %s' % name)
    for downloaded_release in downloaded_releases:
        fire_event('forget', downloaded_release)


def remove_series_episode(name, identifier, forget=False):
    """
    Remove all episodes by `identifier` from series `name` from database.
    :param name: Name of series to be removed
    :param identifier: Series identifier to be deleted
    :param forget: Indication whether or not to fire a 'forget' event
    """
    downloaded_releases = []
    with Session() as session:
        series = session.query(Series).filter(Series.name == name).first()
        if series:
            episode = session.query(Episode).filter(Episode.identifier == identifier). \
                filter(Episode.series_id == series.id).first()
            if episode:
                if not series.begin:
                    series.identified_by = ''  # reset identified_by flag so that it will be recalculated
                if forget:
                    downloaded_releases = [release.title for release in episode.downloaded_releases]
                session.delete(episode)
                log.debug('Episode %s from series %s removed from database.', identifier, name)
            else:
                raise ValueError('Unknown identifier %s for series %s' % (identifier, name.capitalize()))
        else:
            raise ValueError('Unknown series %s' % name)
    for downloaded_release in downloaded_releases:
        fire_event('forget', downloaded_release)


def delete_release_by_id(release_id):
    with Session() as session:
        release = session.query(Release).filter(Release.id == release_id).first()
        if release:
            session.delete(release)
            session.commit()
            log.debug('Deleted release ID %s' % release_id)
        else:
            raise ValueError('Unknown identifier %s for release' % release_id)


def shows_by_name(normalized_name, session=None):
    """ Returns all series matching `normalized_name` """
    return session.query(Series).filter(Series._name_normalized.contains(normalized_name)).order_by(
        func.char_length(Series.name)).all()


def shows_by_exact_name(normalized_name, session=None):
    """ Returns all series matching `normalized_name` """
    return session.query(Series).filter(Series._name_normalized == normalized_name).order_by(
        func.char_length(Series.name)).all()


def show_by_id(show_id, session=None):
    """ Return an instance of a show by querying its ID """
    return session.query(Series).filter(Series.id == show_id).one()


def episode_by_id(episode_id, session=None):
    """ Return an instance of an episode by querying its ID """
    return session.query(Episode).filter(Episode.id == episode_id).one()


def release_by_id(release_id, session=None):
    """ Return an instance of a release by querying its ID """
    return session.query(Release).filter(Release.id == release_id).one()


def show_episodes(series, start=None, stop=None, count=False, descending=False, session=None):
    """ Return all episodes of a given series """
    episodes = session.query(Episode).filter(Episode.series_id == series.id)
    if count:
        return episodes.count()
    # Query episodes in sane order instead of iterating from series.episodes
    if series.identified_by == 'sequence':
        episodes = episodes.order_by(Episode.number.desc()) if descending else episodes.order_by(Episode.number)
    elif series.identified_by == 'ep':
        episodes = episodes.order_by(Episode.season.desc(), Episode.number.desc()) if descending else episodes.order_by(
            Episode.season, Episode.number)
    else:
        episodes = episodes.order_by(Episode.identifier.desc()) if descending else episodes.order_by(Episode.identifier)
    episodes = episodes.slice(start, stop).from_self()
    return episodes.all()


def episode_in_show(series_id, episode_id):
    """ Return True if `episode_id` is part of show with `series_id`, else return False """
    with Session() as session:
        episode = session.query(Episode).filter(Episode.id == episode_id).one()
        return episode.series_id == series_id


def release_in_episode(episode_id, release_id):
    """ Return True if `release_id` is part of episode with `episode_id`, else return False """
    with Session() as session:
        release = session.query(Release).filter(Release.id == release_id).one()
        return release.episode_id == episode_id


def populate_entry_fields(entry, parser, config):
    """
    Populates all series_fields for given entry based on parser.

    :param parser: A valid result from a series parser used to populate the fields.
    :config dict: If supplied, will use 'path' and 'set' options to populate specified fields.
    """
    entry['series_parser'] = copy(parser)
    # add series, season and episode to entry
    entry['series_name'] = parser.name
    if 'quality' in entry and entry['quality'] != parser.quality:
        log.verbose('Found different quality for %s. Was %s, overriding with %s.' %
                    (entry['title'], entry['quality'], parser.quality))
    entry['quality'] = parser.quality
    entry['proper'] = parser.proper
    entry['proper_count'] = parser.proper_count
    entry['release_group'] = parser.group
    if parser.id_type == 'ep':
        entry['series_season'] = parser.season
        entry['series_episode'] = parser.episode
    elif parser.id_type == 'date':
        entry['series_date'] = parser.id
        entry['series_season'] = parser.id.year
    else:
        entry['series_season'] = time.gmtime().tm_year
    entry['series_episodes'] = parser.episodes
    entry['series_id'] = parser.pack_identifier
    entry['series_id_type'] = parser.id_type

    # If a config is passed in, also look for 'path' and 'set' options to set more fields
    if config:
        # set custom download path
        if 'path' in config:
            log.debug('setting %s custom path to %s', entry['title'], config.get('path'))
            # Just add this to the 'set' dictionary, so that string replacement is done cleanly
            config.setdefault('set', {}).update(path=config['path'])

        # accept info from set: and place into the entry
        if 'set' in config:
            set = plugin.get_plugin_by_name('set')
            set.instance.modify(entry, config.get('set'))


class FilterSeriesBase(object):
    """
    Class that contains helper methods for both filter.series as well as plugins that configure it,
    such as all_series, series_premiere and configure_series.
    """

    @property
    def settings_schema(self):
        return {
            'title': 'series options',
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'set': {'type': 'object'},
                'alternate_name': one_or_more({'type': 'string'}),
                # Custom regexp options
                'name_regexp': one_or_more({'type': 'string', 'format': 'regex'}),
                'ep_regexp': one_or_more({'type': 'string', 'format': 'regex'}),
                'date_regexp': one_or_more({'type': 'string', 'format': 'regex'}),
                'sequence_regexp': one_or_more({'type': 'string', 'format': 'regex'}),
                'id_regexp': one_or_more({'type': 'string', 'format': 'regex'}),
                # Date parsing options
                'date_yearfirst': {'type': 'boolean'},
                'date_dayfirst': {'type': 'boolean'},
                # Quality options
                'quality': {'type': 'string', 'format': 'quality_requirements'},
                'qualities': {'type': 'array', 'items': {'type': 'string', 'format': 'quality_requirements'}},
                'timeframe': {'type': 'string', 'format': 'interval'},
                'upgrade': {'type': 'boolean'},
                'target': {'type': 'string', 'format': 'quality_requirements'},
                # Specials
                'specials': {'type': 'boolean'},
                # Propers (can be boolean, or an interval string)
                'propers': {'type': ['boolean', 'string'], 'format': 'interval'},
                # Identified by
                'identified_by': {
                    'type': 'string', 'enum': ['ep', 'date', 'sequence', 'id', 'auto']
                },
                # Strict naming
                'exact': {'type': 'boolean'},
                # Begin takes an ep, sequence or date identifier
                'begin': {
                    'oneOf': [
                        {'name': 'ep identifier', 'type': 'string', 'pattern': r'(?i)^S\d{2,4}E\d{2,3}$',
                         'error_pattern': 'episode identifiers should be in the form `SxxEyy`'},
                        {'name': 'date identifier', 'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$',
                         'error_pattern': 'date identifiers must be in the form `YYYY-MM-DD`'},
                        {'name': 'sequence identifier', 'type': 'integer', 'minimum': 0}
                    ]
                },
                'from_group': one_or_more({'type': 'string'}),
                'parse_only': {'type': 'boolean'},
                'special_ids': one_or_more({'type': 'string'}),
                'prefer_specials': {'type': 'boolean'},
                'assume_special': {'type': 'boolean'},
                'tracking': {'type': ['boolean', 'string'], 'enum': [True, False, 'backfill']}
            },
            'additionalProperties': False
        }

    def make_grouped_config(self, config):
        """Turns a simple series list into grouped format with a empty settings dict"""
        if not isinstance(config, dict):
            # convert simplest configuration internally grouped format
            config = {'simple': config, 'settings': {}}
        else:
            # already in grouped format, just make sure there's settings
            config.setdefault('settings', {})
        return config

    def apply_group_options(self, config):
        """Applies group settings to each item in series group and removes settings dict."""

        # Make sure config is in grouped format first
        config = self.make_grouped_config(config)
        for group_name in config:
            if group_name == 'settings':
                continue
            group_series = []
            if isinstance(group_name, basestring):
                # if group name is known quality, convenience create settings with that quality
                try:
                    qualities.Requirements(group_name)
                    config['settings'].setdefault(group_name, {}).setdefault('target', group_name)
                except ValueError:
                    # If group name is not a valid quality requirement string, do nothing.
                    pass
            for series in config[group_name]:
                # convert into dict-form if necessary
                series_settings = {}
                group_settings = config['settings'].get(group_name, {})
                if isinstance(series, dict):
                    series, series_settings = list(series.items())[0]
                    if series_settings is None:
                        raise Exception('Series %s has unexpected \':\'' % series)
                # Make sure this isn't a series with no name
                if not series:
                    log.warning('Series config contains a series with no name!')
                    continue
                # make sure series name is a string to accommodate for "24"
                if not isinstance(series, basestring):
                    series = str(series)
                # if series have given path instead of dict, convert it into a dict
                if isinstance(series_settings, basestring):
                    series_settings = {'path': series_settings}
                # merge group settings into this series settings
                merge_dict_from_to(group_settings, series_settings)
                # Convert to dict if watched is in SXXEXX format
                if isinstance(series_settings.get('watched'), basestring):
                    season, episode = series_settings['watched'].upper().split('E')
                    season = season.lstrip('S')
                    series_settings['watched'] = {'season': int(season), 'episode': int(episode)}
                # Convert enough to target for backwards compatibility
                if 'enough' in series_settings:
                    log.warning('Series setting `enough` has been renamed to `target` please update your config.')
                    series_settings.setdefault('target', series_settings['enough'])
                # Add quality: 720p if timeframe is specified with no target
                if 'timeframe' in series_settings and 'qualities' not in series_settings:
                    series_settings.setdefault('target', '720p hdtv+')

                group_series.append({series: series_settings})
            config[group_name] = group_series
        del config['settings']
        return config

    def prepare_config(self, config):
        """Generate a list of unique series from configuration.
        This way we don't need to handle two different configuration formats in the logic.
        Applies group settings with advanced form."""

        config = self.apply_group_options(config)
        return self.combine_series_lists(*list(config.values()))

    def combine_series_lists(self, *series_lists, **kwargs):
        """Combines the series from multiple lists, making sure there are no doubles.

        If keyword argument log_once is set to True, an error message will be printed if a series
        is listed more than once, otherwise log_once will be used."""
        unique_series = {}
        for series_list in series_lists:
            for series in series_list:
                series, series_settings = list(series.items())[0]
                if series not in unique_series:
                    unique_series[series] = series_settings
                else:
                    if kwargs.get('log_once'):
                        log_once('Series %s is already configured in series plugin' % series, log)
                    else:
                        log.warning('Series %s is configured multiple times in series plugin.', series)
                    # Combine the config dicts for both instances of the show
                    unique_series[series].update(series_settings)
        # Turn our all_series dict back into a list
        # sort by reverse alpha, so that in the event of 2 series with common prefix, more specific is parsed first
        return [{series: unique_series[series]} for series in sorted(unique_series, reverse=True)]

    def merge_config(self, task, config):
        """Merges another series config dict in with the current one."""

        # Make sure we start with both configs as a list of complex series
        native_series = self.prepare_config(task.config.get('series', {}))
        merging_series = self.prepare_config(config)
        task.config['series'] = self.combine_series_lists(merging_series, native_series, log_once=True)
        return task.config['series']


class FilterSeries(FilterSeriesBase):
    """
    Intelligent filter for tv-series.

    http://flexget.com/wiki/Plugins/series
    """

    @property
    def schema(self):
        return {
            'type': ['array', 'object'],
            # simple format:
            #   - series
            #   - another series
            'items': {
                'type': ['string', 'number', 'object'],
                'additionalProperties': self.settings_schema
            },
            # advanced format:
            #   settings:
            #     group: {...}
            #   group:
            #     {...}
            'properties': {
                'settings': {
                    'type': 'object',
                    'additionalProperties': self.settings_schema
                }
            },
            'additionalProperties': {
                'type': 'array',
                'items': {
                    'type': ['string', 'number', 'object'],
                    'additionalProperties': self.settings_schema
                }
            }
        }

    def __init__(self):
        try:
            self.backlog = plugin.get_plugin_by_name('backlog')
        except plugin.DependencyError:
            log.warning('Unable utilize backlog plugin, episodes may slip trough timeframe')

    def auto_exact(self, config):
        """Automatically enable exact naming option for series that look like a problem"""

        # generate list of all series in one dict
        all_series = {}
        for series_item in config:
            series_name, series_config = list(series_item.items())[0]
            all_series[series_name] = series_config

        # scan for problematic names, enable exact mode for them
        for series_name, series_config in all_series.items():
            for name in list(all_series.keys()):
                if (name.lower().startswith(series_name.lower())) and \
                        (name.lower() != series_name.lower()):
                    if 'exact' not in series_config:
                        log.verbose('Auto enabling exact matching for series %s (reason %s)', series_name, name)
                        series_config['exact'] = True

    # Run after metainfo_quality and before metainfo_series
    @plugin.priority(125)
    def on_task_metainfo(self, task, config):
        config = self.prepare_config(config)
        self.auto_exact(config)
        for series_item in config:
            series_name, series_config = list(series_item.items())[0]
            log.trace('series_name: %s series_config: %s', series_name, series_config)
            start_time = time.clock()
            self.parse_series(task.entries, series_name, series_config)
            took = time.clock() - start_time
            log.trace('parsing %s took %s', series_name, took)

    def on_task_filter(self, task, config):
        """Filter series"""
        # Parsing was done in metainfo phase, create the dicts to pass to process_series from the task entries
        # key: series episode identifier ie. S01E02
        # value: seriesparser

        config = self.prepare_config(config)
        found_series = {}
        for entry in task.entries:
            if entry.get('series_name') and entry.get('series_id') is not None and entry.get('series_parser'):
                found_series.setdefault(entry['series_name'], []).append(entry)

        for series_item in config:
            with Session() as session:
                series_name, series_config = list(series_item.items())[0]
                if series_config.get('parse_only'):
                    log.debug('Skipping filtering of series %s because of parse_only', series_name)
                    continue
                # Make sure number shows (e.g. 24) are turned into strings
                series_name = str(series_name)
                db_series = session.query(Series).filter(Series.name == series_name).first()
                if not db_series:
                    log.debug('adding series %s into db', series_name)
                    db_series = Series()
                    db_series.name = series_name
                    db_series.identified_by = series_config.get('identified_by', 'auto')
                    session.add(db_series)
                    log.debug('-> added %s' % db_series)
                    session.flush()  # Flush to get an id on series before adding alternate names.
                    alts = series_config.get('alternate_name', [])
                    if not isinstance(alts, list):
                        alts = [alts]
                    for alt in alts:
                        _add_alt_name(alt, db_series, series_name, session)
                if series_name not in found_series:
                    continue
                series_entries = {}
                for entry in found_series[series_name]:
                    # store found episodes into database and save reference for later use
                    releases = store_parser(session, entry['series_parser'], series=db_series,
                                            quality=entry.get('quality'))
                    entry['series_releases'] = [r.id for r in releases]
                    series_entries.setdefault(releases[0].episode, []).append(entry)

                # If we didn't find any episodes for this series, continue
                if not series_entries:
                    log.trace('No entries found for %s this run.', series_name)
                    continue

                # configuration always overrides everything
                if series_config.get('identified_by', 'auto') != 'auto':
                    db_series.identified_by = series_config['identified_by']
                # if series doesn't have identified_by flag already set, calculate one now that new eps are added to db
                if not db_series.identified_by or db_series.identified_by == 'auto':
                    db_series.identified_by = auto_identified_by(db_series)
                    log.debug('identified_by set to \'%s\' based on series history', db_series.identified_by)

                log.trace('series_name: %s series_config: %s', series_name, series_config)

                start_time = time.clock()

                self.process_series(task, series_entries, series_config)

                took = time.clock() - start_time
                log.trace('processing %s took %s', series_name, took)

    def parse_series(self, entries, series_name, config):
        """
        Search for `series_name` and populate all `series_*` fields in entries when successfully parsed

        :param session: SQLAlchemy session
        :param entries: List of entries to process
        :param series_name: Series name which is being processed
        :param config: Series config being processed
        """

        def get_as_array(config, key):
            """Return configuration key as array, even if given as a single string"""
            v = config.get(key, [])
            if isinstance(v, basestring):
                return [v]
            return v

        # set parser flags flags based on config / database
        identified_by = config.get('identified_by', 'auto')
        if identified_by == 'auto':
            with Session() as session:
                series = session.query(Series).filter(Series.name == series_name).first()
                if series:
                    # set flag from database
                    identified_by = series.identified_by or 'auto'

        params = dict(identified_by=identified_by,
                      alternate_names=get_as_array(config, 'alternate_name'),
                      name_regexps=get_as_array(config, 'name_regexp'),
                      strict_name=config.get('exact', False),
                      allow_groups=get_as_array(config, 'from_group'),
                      date_yearfirst=config.get('date_yearfirst'),
                      date_dayfirst=config.get('date_dayfirst'),
                      special_ids=get_as_array(config, 'special_ids'),
                      prefer_specials=config.get('prefer_specials'),
                      assume_special=config.get('assume_special'))
        for id_type in SERIES_ID_TYPES:
            params[id_type + '_regexps'] = get_as_array(config, id_type + '_regexp')

        for entry in entries:
            # skip processed entries
            if (entry.get('series_parser') and entry['series_parser'].valid and entry[
                'series_parser'].name.lower() != series_name.lower()):
                continue

            # Quality field may have been manipulated by e.g. assume_quality. Use quality field from entry if available.
            parsed = get_plugin_by_name('parsing').instance.parse_series(entry['title'], name=series_name, **params)
            if not parsed.valid:
                continue
            parsed.field = 'title'

            log.debug('%s detected as %s, field: %s', entry['title'], parsed, parsed.field)
            populate_entry_fields(entry, parsed, config)

    def process_series(self, task, series_entries, config):
        """
        Accept or Reject episode from available releases, or postpone choosing.

        :param task: Current Task
        :param series_entries: dict mapping Episodes to entries for that episode
        :param config: Series configuration
        """

        for ep, entries in series_entries.items():
            if not entries:
                continue

            reason = None

            # sort episodes in order of quality
            entries.sort(key=lambda e: (e['quality'], e['series_parser'].episodes, e['series_parser'].proper_count),
                         reverse=True)

            log.debug('start with episodes: %s', [e['title'] for e in entries])

            # reject episodes that have been marked as watched in config file
            if ep.series.begin:
                if ep < ep.series.begin:
                    for entry in entries:
                        entry.reject('Episode `%s` is before begin value of `%s`' %
                                     (ep.identifier, ep.series.begin.identifier))
                    continue

            # skip special episodes if special handling has been turned off
            if not config.get('specials', True) and ep.identified_by == 'special':
                log.debug('Skipping special episode as support is turned off.')
                continue

            log.debug('current episodes: %s', [e['title'] for e in entries])

            # quality filtering
            if 'quality' in config:
                entries = self.process_quality(config, entries)
                if not entries:
                    continue
                reason = 'matches quality'

            # Many of the following functions need to know this info. Only look it up once.
            downloaded = ep.downloaded_releases
            downloaded_qualities = [rls.quality for rls in downloaded]

            # proper handling
            log.debug('-' * 20 + ' process_propers -->')
            entries = self.process_propers(config, ep, entries)
            if not entries:
                continue

            # Remove any eps we already have from the list
            for entry in reversed(entries):  # Iterate in reverse so we can safely remove from the list while iterating
                if entry['quality'] in downloaded_qualities:
                    entry.reject('quality already downloaded')
                    entries.remove(entry)
            if not entries:
                continue

            # Figure out if we need an additional quality for this ep
            if downloaded:
                if config.get('upgrade'):
                    # Remove all the qualities lower than what we have
                    for entry in reversed(entries):
                        if entry['quality'] < max(downloaded_qualities):
                            entry.reject('worse quality than already downloaded.')
                            entries.remove(entry)
                if not entries:
                    continue

                if 'target' in config and config.get('upgrade'):
                    # If we haven't grabbed the target yet, allow upgrade to it
                    self.process_timeframe_target(config, entries, downloaded)
                    continue
                if 'qualities' in config:
                    # Grab any additional wanted qualities
                    log.debug('-' * 20 + ' process_qualities -->')
                    self.process_qualities(config, entries, downloaded)
                    continue
                elif config.get('upgrade'):
                    entries[0].accept('is an upgrade to existing quality')
                    continue

                # Reject eps because we have them
                for entry in entries:
                    entry.reject('episode has already been downloaded')
                continue

            best = entries[0]
            log.debug('continuing w. episodes: %s', [e['title'] for e in entries])
            log.debug('best episode is: %s', best['title'])

            # episode tracking. used only with season and sequence based series
            if ep.identified_by in ['ep', 'sequence']:
                if task.options.disable_tracking or not config.get('tracking', True):
                    log.debug('episode tracking disabled')
                else:
                    log.debug('-' * 20 + ' episode tracking -->')
                    # Grace is number of distinct eps in the task for this series + 2
                    backfill = config.get('tracking') == 'backfill'
                    if self.process_episode_tracking(ep, entries, grace=len(series_entries) + 2, backfill=backfill):
                        continue

            # quality
            if 'target' in config or 'qualities' in config:
                if 'target' in config:
                    if self.process_timeframe_target(config, entries, downloaded):
                        continue
                elif 'qualities' in config:
                    if self.process_qualities(config, entries, downloaded):
                        continue

                # We didn't make a quality target match, check timeframe to see
                # if we should get something anyway
                if 'timeframe' in config:
                    if self.process_timeframe(task, config, ep, entries):
                        continue
                    reason = 'Timeframe expired, choosing best available'
                else:
                    # If target or qualities is configured without timeframe, don't accept anything now
                    continue

            # Just pick the best ep if we get here
            reason = reason or 'choosing best available quality'
            best.accept(reason)

    def process_propers(self, config, episode, entries):
        """
        Accepts needed propers. Nukes episodes from which there exists proper.

        :returns: A list of episodes to continue processing.
        """

        pass_filter = []
        best_propers = []
        # Since eps is sorted by quality then proper_count we always see the highest proper for a quality first.
        (last_qual, best_proper) = (None, 0)
        for entry in entries:
            if entry['quality'] != last_qual:
                last_qual, best_proper = entry['quality'], entry['series_parser'].proper_count
                best_propers.append(entry)
            if entry['series_parser'].proper_count < best_proper:
                # nuke qualities which there is a better proper available
                entry.reject('nuked')
            else:
                pass_filter.append(entry)

        # If propers support is turned off, or proper timeframe has expired just return the filtered eps list
        if isinstance(config.get('propers', True), bool):
            if not config.get('propers', True):
                return pass_filter
        else:
            # propers with timeframe
            log.debug('proper timeframe: %s', config['propers'])
            timeframe = parse_timedelta(config['propers'])

            first_seen = episode.first_seen
            expires = first_seen + timeframe
            log.debug('propers timeframe: %s', timeframe)
            log.debug('first_seen: %s', first_seen)
            log.debug('propers ignore after: %s', expires)

            if datetime.now() > expires:
                log.debug('propers timeframe expired')
                return pass_filter

        downloaded_qualities = dict((d.quality, d.proper_count) for d in episode.downloaded_releases)
        log.debug('propers - downloaded qualities: %s' % downloaded_qualities)

        # Accept propers we actually need, and remove them from the list of entries to continue processing
        for entry in best_propers:
            if (entry['quality'] in downloaded_qualities and entry['series_parser'].proper_count > downloaded_qualities[
                entry['quality']]):
                entry.accept('proper')
                pass_filter.remove(entry)

        return pass_filter

    def process_timeframe_target(self, config, entries, downloaded=None):
        """
        Accepts first episode matching the quality configured for the series.

        :return: True if accepted something
        """
        req = qualities.Requirements(config['target'])
        if downloaded:
            if any(req.allows(release.quality) for release in downloaded):
                log.debug('Target quality already achieved.')
                return True
        # scan for quality
        for entry in entries:
            if req.allows(entry['quality']):
                log.debug('Series accepting. %s meets quality %s', entry['title'], req)
                entry.accept('target quality')
                return True

    def process_quality(self, config, entries):
        """
        Filters eps that do not fall between within our defined quality standards.

        :returns: A list of eps that are in the acceptable range
        """
        reqs = qualities.Requirements(config['quality'])
        log.debug('quality req: %s', reqs)
        result = []
        # see if any of the eps match accepted qualities
        for entry in entries:
            if reqs.allows(entry['quality']):
                result.append(entry)
            else:
                log.verbose('Ignored `%s`. Does not meet quality requirement `%s`.', entry['title'], reqs)
        if not result:
            log.debug('no quality meets requirements')
        return result

    def process_episode_tracking(self, episode, entries, grace, backfill=False):
        """
        Rejects all episodes that are too old or new, return True when this happens.

        :param episode: Episode model
        :param list entries: List of entries for given episode.
        :param int grace: Number of episodes before or after latest download that are allowed.
        :param bool backfill: If this is True, previous episodes will be allowed,
            but forward advancement will still be restricted.
        """

        latest = get_latest_release(episode.series)
        if episode.series.begin and (not latest or episode.series.begin > latest):
            latest = episode.series.begin
        log.debug('latest download: %s' % latest)
        log.debug('current: %s' % episode)

        if latest and latest.identified_by == episode.identified_by:
            # Allow any previous episodes this season, or previous episodes within grace if sequence mode
            if (not backfill and (episode.season < latest.season or (
                            episode.identified_by == 'sequence' and episode.number < (latest.number - grace)))):
                log.debug('too old! rejecting all occurrences')
                for entry in entries:
                    entry.reject('Too much in the past from latest downloaded episode %s' % latest.identifier)
                return True

            # Allow future episodes within grace, or first episode of next season
            if (episode.season > latest.season + 1 or (episode.season > latest.season and episode.number > 1) or
                    (episode.season == latest.season and episode.number > (latest.number + grace))):
                log.debug('too new! rejecting all occurrences')
                for entry in entries:
                    entry.reject('Too much in the future from latest downloaded episode %s. '
                                 'See `--disable-tracking` if this should be downloaded.' % latest.identifier)
                return True

    def process_timeframe(self, task, config, episode, entries):
        """
        Runs the timeframe logic to determine if we should wait for a better quality.
        Saves current best to backlog if timeframe has not expired.

        :returns: True - if we should keep the quality (or qualities) restriction
                  False - if the quality restriction should be released, due to timeframe expiring
        """

        if 'timeframe' not in config:
            return True

        best = entries[0]

        # parse options
        log.debug('timeframe: %s', config['timeframe'])
        timeframe = parse_timedelta(config['timeframe'])

        if config.get('quality'):
            req = qualities.Requirements(config['quality'])
            seen_times = [rls.first_seen for rls in episode.releases if req.allows(rls.quality)]
        else:
            seen_times = [rls.first_seen for rls in episode.releases]
        # Somehow we can get here without having qualifying releases (#2779) make sure min doesn't crash
        first_seen = min(seen_times) if seen_times else datetime.now()
        expires = first_seen + timeframe
        log.debug('timeframe: %s, first_seen: %s, expires: %s', timeframe, first_seen, expires)

        stop = normalize_series_name(task.options.stop_waiting) == episode.series._name_normalized
        if expires <= datetime.now() or stop:
            # Expire timeframe, accept anything
            log.info('Timeframe expired, releasing quality restriction.')
            return False
        else:
            # verbose waiting, add to backlog
            diff = expires - datetime.now()

            hours, remainder = divmod(diff.seconds, 3600)
            hours += diff.days * 24
            minutes, seconds = divmod(remainder, 60)

            log.info('Timeframe waiting %s for %sh:%smin, currently best is %s' %
                     (episode.series.name, hours, minutes, best['title']))

            # add best entry to backlog (backlog is able to handle duplicate adds)
            if self.backlog:
                self.backlog.instance.add_backlog(task, best, session=object_session(episode))
            return True

    def process_qualities(self, config, entries, downloaded):
        """
        Handles all modes that can accept more than one quality per episode. (qualities, upgrade)

        :returns: True - if at least one wanted quality has been downloaded or accepted.
                  False - if no wanted qualities have been accepted
        """

        # Get list of already downloaded qualities
        downloaded_qualities = [r.quality for r in downloaded]
        log.debug('downloaded_qualities: %s', downloaded_qualities)

        # If qualities key is configured, we only want qualities defined in it.
        wanted_qualities = set([qualities.Requirements(name) for name in config.get('qualities', [])])
        # Compute the requirements from our set that have not yet been fulfilled
        still_needed = [req for req in wanted_qualities if not any(req.allows(qual) for qual in downloaded_qualities)]
        log.debug('Wanted qualities: %s', wanted_qualities)

        def wanted(quality):
            """Returns True if we want this quality based on the config options."""
            wanted = not wanted_qualities or any(req.allows(quality) for req in wanted_qualities)
            if config.get('upgrade'):
                wanted = wanted and quality > max(downloaded_qualities or [qualities.Quality()])
            return wanted

        for entry in entries:
            quality = entry['quality']
            log.debug('ep: %s quality: %s', entry['title'], quality)
            if not wanted(quality):
                log.debug('%s is unwanted quality', quality)
                continue
            if any(req.allows(quality) for req in still_needed):
                # Don't get worse qualities in upgrade mode
                if config.get('upgrade'):
                    if downloaded_qualities and quality < max(downloaded_qualities):
                        continue
                entry.accept('quality wanted')
                downloaded_qualities.append(quality)
                downloaded.append(entry)
                # Re-calculate what is still needed
                still_needed = [req for req in still_needed if not req.allows(quality)]
        return bool(downloaded_qualities)

    def on_task_learn(self, task, config):
        """Learn succeeded episodes"""
        log.debug('on_task_learn')
        for entry in task.accepted:
            if 'series_releases' in entry:
                with Session() as session:
                    num = (session.query(Release).filter(Release.id.in_(entry['series_releases'])).
                           update({'downloaded': True}, synchronize_session=False))
                log.debug('marking %s releases as downloaded for %s', num, entry)
            else:
                log.debug('%s is not a series', entry['title'])


class SeriesDBManager(FilterSeriesBase):
    """Update in the database with series info from the config"""

    @plugin.priority(0)
    def on_task_start(self, task, config):
        if not task.config_modified:
            return
        # Clear all series from this task
        with Session() as session:
            session.query(SeriesTask).filter(SeriesTask.name == task.name).delete()
            if not task.config.get('series'):
                return
            config = self.prepare_config(task.config['series'])
            for series_item in config:
                series_name, series_config = list(series_item.items())[0]
                # Make sure number shows (e.g. 24) are turned into strings
                series_name = str(series_name)
                db_series = session.query(Series).filter(Series.name == series_name).first()
                alts = series_config.get('alternate_name', [])
                if not isinstance(alts, list):
                    alts = [alts]
                if db_series:
                    # Update database with capitalization from config
                    db_series.name = series_name
                    # Remove the alternate names not present in current config
                    db_series.alternate_names = [alt for alt in db_series.alternate_names if alt.alt_name in alts]
                    # Add/update the possibly new alternate names
                else:
                    log.debug('adding series %s into db', series_name)
                    db_series = Series()
                    db_series.name = series_name
                    session.add(db_series)
                    session.flush()  # flush to get id on series before creating alternate names
                    log.debug('-> added %s' % db_series)
                for alt in alts:
                    _add_alt_name(alt, db_series, series_name, session)
                db_series.in_tasks.append(SeriesTask(task.name))
                if series_config.get('identified_by', 'auto') != 'auto':
                    db_series.identified_by = series_config['identified_by']
                # Set the begin episode
                if series_config.get('begin'):
                    try:
                        set_series_begin(db_series, series_config['begin'])
                    except ValueError as e:
                        raise plugin.PluginError(e)


def _add_alt_name(alt, db_series, series_name, session):
    alt = str(alt)
    db_series_alt = session.query(AlternateNames).filter(AlternateNames.alt_name == alt).first()
    if db_series_alt and db_series_alt.series_id == db_series.id:
        # Already exists, no need to create it then
        # TODO is checking the list for duplicates faster/better than querying the DB?
        db_series_alt.alt_name = alt
    elif db_series_alt:
        if not db_series_alt.series:
            # Not sure how this can happen
            log.debug('Found an alternate name not attached to series. Re-attatching %s to %s' % (alt, series_name))
            db_series.alternate_names.append(db_series_alt)
        else:
            # Alternate name already exists for another series. Not good.
            raise plugin.PluginError('Error adding alternate name for %s. %s is already associated with %s. '
                                     'Check your settings.' % (series_name, alt, db_series_alt.series.name))
    else:
        log.debug('adding alternate name %s for %s into db' % (alt, series_name))
        db_series_alt = AlternateNames(alt)
        db_series.alternate_names.append(db_series_alt)
        log.debug('-> added %s' % db_series_alt)


def set_alt_names(alt_names, db_series, session):
    db_alt_names = []
    for alt_name in alt_names:
        db_series_alt = session.query(AlternateNames).filter(AlternateNames.alt_name == alt_name).first()
        if db_series_alt:
            if not db_series_alt.series_id == db_series.id:
                raise plugin.PluginError('Error adding alternate name for %s. "%s" is already associated with %s. '
                                         'Check your settings.' % (db_series.name, alt_name, db_series_alt.series.name))
            else:
                log.debug('alternate name %s already associated with series %s, no change needed', alt_name,
                          db_series.name)
                db_alt_names.append(db_series_alt)
        else:
            db_alt_names.append(AlternateNames(alt_name))
            log.debug('adding alternate name %s to series %s', alt_name, db_series.name)
    db_series.alternate_names[:] = db_alt_names


@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeries, 'series', api_ver=2)
    # This is a builtin so that it can update the database for tasks that may have had series plugin removed
    plugin.register(SeriesDBManager, 'series_db', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    exec_parser.add_argument('--stop-waiting', action='store', dest='stop_waiting', default='',
                             metavar='NAME', help='stop timeframe for a given series')
    exec_parser.add_argument('--disable-tracking', action='store_true', default=False,
                             help='disable episode advancement for this run')
    # Backwards compatibility
    exec_parser.add_argument('--disable-advancement', action='store_true', dest='disable_tracking',
                             help=argparse.SUPPRESS)
