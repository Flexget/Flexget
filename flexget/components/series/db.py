import re
from datetime import datetime, timedelta
from functools import total_ordering
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Union

from loguru import logger
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Unicode,
    and_,
    delete,
    desc,
    func,
    select,
    update,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import backref, relation

from flexget import db_schema, plugin
from flexget.components.series.utils import normalize_series_name
from flexget.event import event, fire_event
from flexget.manager import Session
from flexget.utils.database import quality_property, with_session
from flexget.utils.sqlalchemy_utils import (
    create_index,
    drop_tables,
    table_add_column,
    table_columns,
    table_exists,
    table_schema,
)
from flexget.utils.tools import parse_episode_identifier

if TYPE_CHECKING:
    from flexget.components.parsing.parsers.parser_common import SeriesParseResult
    from flexget.utils.qualities import Quality


SCHEMA_VER = 14
logger = logger.bind(name='series.db')
Base = db_schema.versioned_base('series', SCHEMA_VER)


class NormalizedComparator(Comparator):
    def operate(self, op, other):
        if isinstance(other, list):
            other = [normalize_series_name(o) for o in other]
        else:
            other = normalize_series_name(other)

        return op(self.__clause_element__(), other)


class Series(Base):
    """Name is handled case insensitively transparently"""

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    _name = Column('name', Unicode)
    _name_normalized = Column('name_lower', Unicode, index=True, unique=True)
    identified_by = Column(String)
    begin_episode_id = Column(
        Integer, ForeignKey('series_episodes.id', name='begin_episode_id', use_alter=True)
    )
    begin = relation(
        'Episode',
        uselist=False,
        primaryjoin="Series.begin_episode_id == Episode.id",
        foreign_keys=[begin_episode_id],
        post_update=True,
        backref='begins_series',
    )
    episodes = relation(
        'Episode',
        backref='series',
        cascade='all, delete, delete-orphan',
        primaryjoin='Series.id == Episode.series_id',
    )
    in_tasks = relation(
        'SeriesTask',
        backref=backref('series', uselist=False),
        cascade='all, delete, delete-orphan',
    )
    alternate_names = relation(
        'AlternateNames', backref='series', cascade='all, delete, delete-orphan'
    )

    seasons = relation('Season', backref='series', cascade='all, delete, delete-orphan')

    # Make a special property that does indexed case insensitive lookups on name, but stores/returns specified case
    @hybrid_property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._name_normalized = normalize_series_name(value)

    @name.comparator
    def name(self):
        return NormalizedComparator(self._name_normalized)

    @property
    def name_normalized(self):
        return self._name_normalized

    def __str__(self):
        return f'<Series(id={self.id},name={self.name})>'

    def __repr__(self):
        return str(self).encode('ascii', 'replace')

    def episodes_for_season(self, season_num):
        return len(
            [
                episode
                for episode in self.episodes
                if episode.season == season_num and episode.downloaded_releases
            ]
        )

    @property
    def completed_seasons(self):
        return [season.season for season in self.seasons if season.completed]


class Season(Base):
    __tablename__ = 'series_seasons'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)

    identified_by = Column(String)
    season = Column(Integer)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)

    releases = relation('SeasonRelease', backref='season', cascade='all, delete, delete-orphan')

    is_season = True

    @property
    def completed(self):
        """
        Return True if the season has any released marked as downloaded
        """
        if not self.releases:
            return False
        return any(release.downloaded for release in self.releases)

    @property
    def downloaded_releases(self):
        return [release for release in self.releases if release.downloaded]

    @hybrid_property
    def first_seen(self):
        if not self.releases:
            return None
        return min(release.first_seen for release in self.releases)

    @first_seen.expression
    def first_seen(cls):
        return (
            select([func.min(SeasonRelease.first_seen)])
            .where(SeasonRelease.season_id == cls.id)
            .correlate(Season.__table__)
            .label('first_seen')
        )

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
    def age_timedelta(self):
        """
        :return: Timedelta or None if seasons is never seen
        """
        if not self.first_seen:
            return None
        return datetime.now() - self.first_seen

    @property
    def is_premiere(self):
        return False

    def __str__(self):
        return '<Season(id={},identifier={},season={},completed={})>'.format(
            self.id,
            self.identifier,
            self.season,
            self.completed,
        )

    def __repr__(self):
        return str(self).encode('ascii', 'replace')

    def __lt__(self, other):
        if other is None:
            logger.trace('comparing {} to None', self)
            return False
        if not isinstance(other, (Season, Episode)):
            logger.error('Cannot compare Season to {}', other)
            return NotImplemented
        if self.identified_by != 'ep':
            logger.error('Can only compare with an \'ep\' style identifier')
            return NotImplemented
        logger.trace('checking if {} is smaller than {}', self.season, other.season)
        return self.season < other.season

    def __hash__(self):
        return self.id

    def to_dict(self):
        return {
            'id': self.id,
            'identifier': self.identifier,
            'season': self.season,
            'identified_by': self.identified_by,
            'series_id': self.series_id,
            'first_seen': self.first_seen,
            'number_of_releases': len(self.releases),
        }

    @property
    def latest_release(self):
        """
        :return: Latest downloaded Release or None
        """
        if not self.releases:
            return None
        return sorted(
            self.downloaded_releases,
            key=lambda rel: rel.first_seen if rel.downloaded else None,
            reverse=True,
        )[0]


@total_ordering
class Episode(Base):
    __tablename__ = 'series_episodes'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)

    season = Column(Integer)
    number = Column(Integer)

    identified_by = Column(String)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    releases = relation('EpisodeRelease', backref='episode', cascade='all, delete, delete-orphan')

    is_season = False

    @hybrid_property
    def first_seen(self):
        if not self.releases:
            return None
        return min(release.first_seen for release in self.releases)

    @first_seen.expression
    def first_seen(cls):
        return (
            select([func.min(EpisodeRelease.first_seen)])
            .where(EpisodeRelease.episode_id == cls.id)
            .correlate(Episode.__table__)
            .label('first_seen')
        )

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
    def age_timedelta(self):
        """
        :return: Timedelta or None if episode is never seen
        """
        if not self.first_seen:
            return None
        return datetime.now() - self.first_seen

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

    @property
    def latest_release(self):
        """
        :return: Latest downloaded Release or None
        """
        if not self.releases:
            return None
        return sorted(
            self.downloaded_releases,
            key=lambda rel: rel.first_seen if rel.downloaded else None,
            reverse=True,
        )[0]

    def __str__(self):
        return '<Episode(id={},identifier={},season={},number={})>'.format(
            self.id,
            self.identifier,
            self.season,
            self.number,
        )

    def __repr__(self):
        return str(self).encode('ascii', 'replace')

    def __eq__(self, other):
        if other is None:
            logger.trace('comparing {} to None', self)
            return False
        if isinstance(other, Season):
            logger.trace('comparing {} to Season', self)
            return False
        elif not isinstance(other, Episode):
            logger.error('Cannot compare Episode with {}', other)
            return NotImplemented
        if self.identified_by != other.identified_by:
            logger.error(
                'Cannot compare {} identifier with {}', self.identified_by, other.identified_by
            )
            return NotImplemented
        logger.trace('comparing {} with {}', self.identifier, other.identifier)
        return self.identifier == other.identifier

    def __lt__(self, other):
        if other is None:
            logger.trace('comparing {} to None', self)
            return False
        elif isinstance(other, Episode):
            if self.identified_by is None or other.identified_by is None:
                bad_ep = other if other.identified_by is None else self
                logger.error('cannot compare episode without an identifier type: {}', bad_ep)
                return False
            if self.identified_by != other.identified_by:
                if self.identified_by == 'special':
                    logger.trace('Comparing special episode')
                    return False
                logger.error('cannot compare {} with {}', self.identified_by, other.identified_by)
                return NotImplemented
            if self.identified_by in ['ep', 'sequence']:
                logger.trace('comparing {} and {}', self, other)
                return self.season < other.season or (
                    self.season == other.season and self.number < other.number
                )
            elif self.identified_by == 'date':
                logger.trace('comparing {} and {}', self.identifier, other.identifier)
                return self.identifier < other.identifier
            else:
                logger.error('cannot compare when identifier is {}', self.identified_by)
                return NotImplemented
        elif isinstance(other, Season):
            if self.identified_by != 'ep':
                logger.error('cannot compare season when identifier is not \'ep\'')
                return NotImplemented
            logger.trace('comparing {} with {}', self.season, other.season)
            return self.season < other.season
        else:
            logger.error('can only compare with Episode or Season, not {}', other)
            return NotImplemented

    def __hash__(self):
        return self.id

    def to_dict(self):
        return {
            'id': self.id,
            'identifier': self.identifier,
            'season': self.season,
            'identified_by': self.identified_by,
            'number': self.number,
            'series_id': self.series_id,
            'first_seen': self.first_seen,
            'premiere': self.is_premiere,
            'number_of_releases': len(self.releases),
        }


class EpisodeRelease(Base):
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
        return '<Release(id={},quality={},downloaded={},proper_count={},title={})>'.format(
            self.id,
            self.quality,
            self.downloaded,
            self.proper_count,
            self.title,
        )

    def __repr__(self):
        return str(self).encode('ascii', 'replace')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'downloaded': self.downloaded,
            'quality': self.quality.name,
            'proper_count': self.proper_count,
            'first_seen': self.first_seen,
            'episode_id': self.episode_id,
        }


class SeasonRelease(Base):
    __tablename__ = 'season_releases'

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey('series_seasons.id'), nullable=False, index=True)

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
        return '<Release(id={},quality={},downloaded={},proper_count={},title={})>'.format(
            self.id,
            self.quality,
            self.downloaded,
            self.proper_count,
            self.title,
        )

    def __repr__(self):
        return str(self).encode('ascii', 'replace')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'downloaded': self.downloaded,
            'quality': self.quality.name,
            'proper_count': self.proper_count,
            'first_seen': self.first_seen,
            'season_id': self.season_id,
        }


class AlternateNames(Base):
    """Similar to Series. Name is handled case insensitively transparently."""

    __tablename__ = 'series_alternate_names'
    id = Column(Integer, primary_key=True)
    _alt_name = Column('alt_name', Unicode)
    _alt_name_normalized = Column('alt_name_normalized', Unicode, index=True, unique=True)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)

    @hybrid_property
    def alt_name(self):
        return self._alt_name

    @alt_name.setter
    def alt_name(self, value):
        self._alt_name = value
        self._alt_name_normalized = normalize_series_name(value)

    @alt_name.comparator
    def alt_name(self):
        return NormalizedComparator(self._alt_name_normalized)

    @property
    def name_normalized(self):
        return self._alt_name_normalized

    def __init__(self, name):
        self.alt_name = name

    def __str__(self):
        return '<SeriesAlternateName(series_id={}, alt_name={})>'.format(
            self.series_id, self.alt_name
        )

    def __repr__(self):
        return str(self).encode('ascii', 'replace')


class SeriesTask(Base):
    __tablename__ = 'series_tasks'

    id = Column(Integer, primary_key=True)
    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    name = Column(Unicode, index=True)

    def __init__(self, name):
        self.name = name


Index('episode_series_identifier', Episode.series_id, Episode.identifier)


@db_schema.upgrade('series')
def upgrade(ver: Optional[int], session: Session) -> int:
    if ver is None:
        if table_exists('episode_qualities', session):
            logger.info(
                'Series database format is too old to upgrade, dropping and recreating tables.'
            )
            # Drop the deprecated data
            drop_tables(['series', 'series_episodes', 'episode_qualities'], session)
            # Create new tables from the current models
            Base.metadata.create_all(bind=session.bind)
        # Upgrade episode_releases table to have a proper count and seed it with appropriate numbers
        columns = table_columns('episode_releases', session)
        if 'proper_count' not in columns:
            logger.info('Upgrading episode_releases table to have proper_count column')
            table_add_column('episode_releases', 'proper_count', Integer, session)
            release_table = table_schema('episode_releases', session)
            for row in session.execute(select([release_table.c.id, release_table.c.title])):
                # Recalculate the proper_count from title for old episodes
                proper_count = (
                    plugin.get('parsing', 'series.db').parse_series(row['title']).proper_count
                )
                session.execute(
                    update(
                        release_table,
                        release_table.c.id == row['id'],
                        {'proper_count': proper_count},
                    )
                )
        ver = 0
    if ver == 0:
        logger.info('Migrating first_seen column from series_episodes to episode_releases table.')
        # Create the column in episode_releases
        table_add_column('episode_releases', 'first_seen', DateTime, session)
        # Seed the first_seen value for all the past releases with the first_seen of their episode.
        episode_table = table_schema('series_episodes', session)
        release_table = table_schema('episode_releases', session)
        for row in session.execute(select([episode_table.c.id, episode_table.c.first_seen])):
            session.execute(
                update(
                    release_table,
                    release_table.c.episode_id == row['id'],
                    {'first_seen': row['first_seen']},
                )
            )
        ver = 1
    if ver == 1:
        logger.info('Adding `identified_by` column to series table.')
        table_add_column('series', 'identified_by', String, session)
        ver = 2
    if ver == 2:
        logger.info('Creating index on episode_releases table.')
        create_index('episode_releases', session, 'episode_id')
        ver = 3
    if ver == 3:
        # Remove index on Series.name
        try:
            session.execute("DROP INDEX ix_series_name")
            # This way doesn't work on sqlalchemy 1.4 for some reason
            # Index('ix_series_name').drop(bind=session.bind)
        except OperationalError:
            logger.debug('There was no ix_series_name index to remove.')
        # Add Series.name_lower column
        logger.info('Adding `name_lower` column to series table.')
        table_add_column('series', 'name_lower', Unicode, session)
        series_table = table_schema('series', session)
        create_index('series', session, 'name_lower')
        # Fill in lower case name column
        session.execute(
            update(series_table, values={'name_lower': func.lower(series_table.c.name)})
        )
        ver = 4
    if ver == 4:
        logger.info('Adding `identified_by` column to episodes table.')
        table_add_column('series_episodes', 'identified_by', String, session)
        series_table = table_schema('series', session)
        # Clear out identified_by id series so that they can be auto detected again
        session.execute(
            update(series_table, series_table.c.identified_by != 'ep', {'identified_by': None})
        )
        # Warn users about a possible config change needed.
        logger.warning(
            'If you are using `identified_by: id` for the series plugin for a date-identified '
            'or abolute-numbered series, you will need to update your config. Two new identified_by modes have '
            'been added: `date` and `sequence`. In addition, if you are using `identified_by: auto`, it will'
            'be relearned based on upcoming episodes.'
        )
        ver = 5
    if ver == 5:
        # Episode advancement now relies on identified_by being filled for the episodes.
        # This action retroactively marks 'ep' mode for all episodes where the series is already in 'ep' mode.
        series_table = table_schema('series', session)
        ep_table = table_schema('series_episodes', session)
        ep_mode_series = select([series_table.c.id], series_table.c.identified_by == 'ep')
        where_clause = and_(
            ep_table.c.series_id.in_(ep_mode_series),
            ep_table.c.season != None,
            ep_table.c.number != None,
            ep_table.c.identified_by == None,
        )
        session.execute(update(ep_table, where_clause, {'identified_by': 'ep'}))
        ver = 6
    if ver == 6:
        # Translate old qualities into new quality requirements
        release_table = table_schema('episode_releases', session)
        for row in session.execute(select([release_table.c.id, release_table.c.quality])):
            # Webdl quality no longer has dash
            new_qual = row['quality'].replace('web-dl', 'webdl')
            if row['quality'] != new_qual:
                session.execute(
                    update(release_table, release_table.c.id == row['id'], {'quality': new_qual})
                )
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
            session.execute(
                update(series_table, series_table.c.id == ids[0], {'name_lower': series})
            )
        ver = 9
    if ver == 9:
        table_add_column('series', 'begin_episode_id', Integer, session)
        ver = 10
    if ver == 10:
        # Due to bad db cleanups there may be invalid entries in series_tasks table
        series_tasks = table_schema('series_tasks', session)
        series_table = table_schema('series', session)
        logger.verbose('Repairing series_tasks table data')
        session.execute(
            delete(series_tasks, ~series_tasks.c.series_id.in_(select([series_table.c.id])))
        )
        ver = 11
    if ver == 11:
        # SeriesTasks was cleared out due to a bug, make sure they get recalculated next run #2772
        from flexget.task import config_changed

        config_changed(session=session)
        ver = 12
    if ver == 12:
        # Force identified_by value None to 'auto'
        series_table = table_schema('series', session)
        session.execute(
            update(series_table, series_table.c.identified_by == None, {'identified_by': 'auto'})
        )
        ver = 13
    if ver == 13:
        # New season_releases table, added by "create_all"
        logger.info('Adding season_releases table')
        ver = 14
    return ver


@event('manager.db_cleanup')
def db_cleanup(manager, session: Session) -> None:
    # Clean up old undownloaded releases
    result = (
        session.query(EpisodeRelease)
        .filter(EpisodeRelease.downloaded == False)
        .filter(EpisodeRelease.first_seen < datetime.now() - timedelta(days=120))
        .delete(False)
    )
    if result:
        logger.verbose('Removed {} undownloaded episode releases.', result)
    # Clean up episodes without releases
    result = (
        session.query(Episode)
        .filter(~Episode.releases.any())
        .filter(~Episode.begins_series.any())
        .delete(False)
    )
    if result:
        logger.verbose('Removed {} episodes without releases.', result)
    # Clean up series without episodes that aren't in any tasks
    result = (
        session.query(Series)
        .filter(~Series.episodes.any())
        .filter(~Series.in_tasks.any())
        .delete(False)
    )
    if result:
        logger.verbose('Removed {} series without episodes.', result)


def set_alt_names(alt_names: Iterable[str], db_series: Series, session: Session) -> None:
    db_alt_names = []
    for alt_name in alt_names:
        db_series_alt = (
            session.query(AlternateNames).filter(AlternateNames.alt_name == alt_name).first()
        )
        if db_series_alt:
            if not db_series_alt.series_id == db_series.id:
                raise plugin.PluginError(
                    'Error adding alternate name for `{}`: `{}` is already associated with `{}`. '
                    'Check your settings.'.format(
                        db_series.name, alt_name, db_series_alt.series.name
                    )
                )
            else:
                logger.debug(
                    'alternate name `{}` already associated with series `{}`, no change needed',
                    alt_name,
                    db_series.name,
                )
                db_alt_names.append(db_series_alt)
        else:
            db_alt_names.append(AlternateNames(alt_name))
            logger.debug('adding alternate name `{}` to series `{}`', alt_name, db_series.name)
    db_series.alternate_names[:] = db_alt_names


def show_seasons(
    series: Series,
    start: int = None,
    stop: int = None,
    count: bool = False,
    descending: bool = False,
    session: Session = None,
) -> Union[int, List[Season]]:
    """Return all seasons of a given series"""
    seasons = session.query(Season).filter(Season.series_id == series.id)
    if count:
        return seasons.count()
    seasons = (
        seasons.order_by(Season.season.desc()) if descending else seasons.order_by(Season.season)
    )
    return seasons.slice(start, stop).from_self().all()


def get_all_entities(
    series: Series, session: Session, sort_by: str = 'age', reverse: bool = False
) -> List[Union[Episode, Season]]:
    episodes = show_episodes(series, session=session)
    seasons = show_seasons(series, session=session)
    if sort_by == 'identifier':

        def key(e):
            return e.identifier

    else:

        def key(e):
            return e.first_seen or datetime.min, e.identifier

    return sorted(episodes + seasons, key=key, reverse=reverse)


def get_episode_releases(
    episode: Episode,
    downloaded: bool = None,
    start: int = None,
    stop: int = None,
    count: bool = False,
    descending: bool = False,
    sort_by: str = None,
    session: Session = None,
) -> List[EpisodeRelease]:
    """Return all releases for a given episode"""
    releases = session.query(EpisodeRelease).filter(EpisodeRelease.episode_id == episode.id)
    if downloaded is not None:
        releases = releases.filter(EpisodeRelease.downloaded == downloaded)
    if count:
        return releases.count()
    releases = releases.slice(start, stop).from_self()
    if descending:
        releases = releases.order_by(getattr(EpisodeRelease, sort_by).desc())
    else:
        releases = releases.order_by(getattr(EpisodeRelease, sort_by))
    return releases.all()


def get_season_releases(
    season: Season,
    downloaded: bool = None,
    start: int = None,
    stop: int = None,
    count: bool = False,
    descending: bool = False,
    sort_by: str = None,
    session: Session = None,
) -> Union[int, List[SeasonRelease]]:
    """Return all releases for a given season"""
    releases = session.query(SeasonRelease).filter(SeasonRelease.season_id == season.id)
    if downloaded is not None:
        releases = releases.filter(SeasonRelease.downloaded == downloaded)
    if count:
        return releases.count()
    releases = releases.slice(start, stop).from_self()
    if descending:
        releases = releases.order_by(getattr(SeasonRelease, sort_by).desc())
    else:
        releases = releases.order_by(getattr(SeasonRelease, sort_by))
    return releases.all()


def episode_in_show(series_id: int, episode_id: int) -> bool:
    """Return True if `episode_id` is part of show with `series_id`, else return False"""
    with Session() as session:
        episode = session.query(Episode).filter(Episode.id == episode_id).one()
        return episode.series_id == series_id


def season_in_show(series_id: int, season_id: int) -> bool:
    """Return True if `episode_id` is part of show with `series_id`, else return False"""
    with Session() as session:
        season = session.query(Season).filter(Season.id == season_id).one()
        return season.series_id == series_id


def release_in_episode(episode_id: int, release_id: int) -> bool:
    """Return True if `release_id` is part of episode with `episode_id`, else return False"""
    with Session() as session:
        release = session.query(EpisodeRelease).filter(EpisodeRelease.id == release_id).one()
        return release.episode_id == episode_id


def release_in_season(season_id: int, release_id: int) -> bool:
    """Return True if `release_id` is part of episode with `episode_id`, else return False"""
    with Session() as session:
        release = session.query(SeasonRelease).filter(SeasonRelease.id == release_id).one()
        return release.season_id == season_id


def _add_alt_name(alt: str, db_series: Series, series_name: str, session: Session) -> None:
    alt = str(alt)
    db_series_alt = session.query(AlternateNames).filter(AlternateNames.alt_name == alt).first()
    if db_series_alt and db_series_alt.series_id == db_series.id:
        # Already exists, no need to create it then
        # TODO is checking the list for duplicates faster/better than querying the DB?
        db_series_alt.alt_name = alt
    elif db_series_alt:
        if not db_series_alt.series:
            # Not sure how this can happen
            logger.debug(
                'Found an alternate name not attached to series. Re-attatching `{}` to `{}`.',
                alt,
                series_name,
            )
            db_series.alternate_names.append(db_series_alt)
        else:
            # Alternate name already exists for another series. Not good.
            raise plugin.PluginError(
                'Error adding alternate name for `{}`: `{}` is already associated with `{}`. '
                'Check your settings.'.format(series_name, alt, db_series_alt.series.name)
            )
    else:
        logger.debug('adding alternate name `{}` for `{}` into db', alt, series_name)
        db_series_alt = AlternateNames(alt)
        db_series.alternate_names.append(db_series_alt)
        logger.debug('-> added {}', db_series_alt)


@with_session
def get_series_summary(
    configured: str = None,
    premieres: bool = None,
    start: int = None,
    stop: int = None,
    count: bool = False,
    sort_by: str = 'show_name',
    descending: bool = None,
    session: Session = None,
    name: str = None,
) -> Union[int, Iterable[Series]]:
    """
    Return a query with results for all series.

    :param configured: 'configured' for shows in config, 'unconfigured' for shows not in config, 'all' for both.
        Default is 'all'
    :param premieres: Return only shows with 1 season and less than 3 episodes
    :param count: Decides whether to return count of all shows or data itself
    :param session: Passed session
    :return:
    """
    if not configured:
        configured = 'configured'
    elif configured not in ['configured', 'unconfigured', 'all']:
        raise LookupError(
            '"configured" parameter must be either "configured", "unconfigured", or "all"'
        )
    query = session.query(Series)
    query = (
        query.outerjoin(Series.episodes)
        .outerjoin(Episode.releases)
        .outerjoin(Series.in_tasks)
        .group_by(Series.id)
    )
    if configured == 'configured':
        query = query.having(func.count(SeriesTask.id) >= 1)
    elif configured == 'unconfigured':
        query = query.having(func.count(SeriesTask.id) < 1)
    if name:
        query = query.filter(Series._name_normalized.contains(name))
    if premieres:
        query = (
            query.having(func.max(Episode.season) <= 1).having(func.max(Episode.number) <= 2)
        ).filter(EpisodeRelease.downloaded == True)
    if count:
        return query.group_by(Series).count()
    if sort_by == 'show_name':
        order_by = Series.name
    else:
        order_by = func.max(EpisodeRelease.first_seen)
    query = query.order_by(desc(order_by)) if descending else query.order_by(order_by)

    return query.slice(start, stop).from_self()


def auto_identified_by(series: Series) -> str:
    """
    Determine if series `name` should be considered identified by episode or id format

    Returns 'ep', 'sequence', 'date' or 'id' if enough history is present to identify the series' id type.
    Returns 'auto' if there is not enough history to determine the format yet
    """

    session = Session.object_session(series)
    type_totals = dict(
        session.query(Episode.identified_by, func.count(Episode.identified_by))
        .join(Episode.series)
        .filter(Series.id == series.id)
        .group_by(Episode.identified_by)
        .all()
    )
    # Remove None and specials from the dict,
    # we are only considering episodes that we know the type of (parsed with new parser)
    type_totals.pop(None, None)
    type_totals.pop('special', None)
    if not type_totals:
        return 'auto'
    logger.debug('{} episode type totals: {!r}', series.name, type_totals)
    # Find total number of parsed episodes
    total = sum(type_totals.values())
    # See which type has the most
    best = max(type_totals, key=lambda x: type_totals[x])

    # Ep mode locks in faster than the rest. At 2 seen episodes.
    if type_totals.get('ep', 0) >= 2 and type_totals['ep'] > total / 3:
        logger.info('identified_by has locked in to type `ep` for {}', series.name)
        return 'ep'
    # If we have over 3 episodes all of the same type, lock in
    if len(type_totals) == 1 and total >= 3:
        return best
    # Otherwise wait until 5 episodes to lock in
    if total >= 5:
        logger.info('identified_by has locked in to type `{}` for {}', best, series.name)
        return best
    logger.verbose(
        'identified by is currently on `auto` for {}. '
        'Multiple id types may be accepted until it locks in on the appropriate type.',
        series.name,
    )
    return 'auto'


def get_latest_season_pack_release(
    series: Series, downloaded: bool = True, season: int = None
) -> Optional[Season]:
    """
    Return the latest season pack release for a series

    :param Series series: Series object
    :param bool downloaded: Flag to return only downloaded season packs
    :param season: Filter by season number
    :return: Latest release of a season object
    """
    session = Session.object_session(series)
    releases = (
        session.query(Season).join(Season.releases, Season.series).filter(Series.id == series.id)
    )

    if downloaded:
        releases = releases.filter(SeasonRelease.downloaded == True)

    if season is not None:
        releases = releases.filter(Season.season == season)

    latest_season_pack_release = releases.order_by(desc(Season.season)).first()
    if not latest_season_pack_release:
        logger.debug(
            'no season packs found for series `{}` with parameters season: {}, downloaded: {}',
            series.name,
            season,
            downloaded,
        )
        return
    logger.debug(
        'latest season pack for series {}, with downloaded set to {} and season set to {}',
        series,
        downloaded,
        season,
    )
    return latest_season_pack_release


def get_latest_episode_release(
    series: Series, downloaded: bool = True, season: int = None
) -> Optional[Episode]:
    """
    :param series series: SQLAlchemy session
    :param downloaded: find only downloaded releases
    :param season: season to find newest release for
    :return: Instance of Episode or None if not found.
    """
    session = Session.object_session(series)
    releases = (
        session.query(Episode)
        .join(Episode.releases, Episode.series)
        .filter(Series.id == series.id)
    )

    if downloaded:
        releases = releases.filter(EpisodeRelease.downloaded == True)

    if season is not None:
        releases = releases.filter(Episode.season == season)

    if series.identified_by and series.identified_by != 'auto':
        releases = releases.filter(Episode.identified_by == series.identified_by)

    if series.identified_by in ['ep', 'sequence']:
        latest_episode_release = releases.order_by(
            desc(Episode.season), desc(Episode.number)
        ).first()
    elif series.identified_by == 'date':
        latest_episode_release = releases.order_by(desc(Episode.identifier)).first()
    else:
        # We have to label the order_by clause to disambiguate from Release.first_seen #3055
        latest_episode_release = releases.order_by(
            desc(Episode.first_seen.label('ep_first_seen'))
        ).first()

    if not latest_episode_release:
        logger.debug(
            'no episodes found for series `{}` with parameters season: {}, downloaded: {}',
            series.name,
            season,
            downloaded,
        )
        return
    logger.debug(
        'latest episode for series {}, with downloaded set to {} and season set to {}',
        series,
        downloaded,
        season,
    )
    return latest_episode_release


def get_latest_release(
    series: Series, downloaded: bool = True, season: int = None
) -> Union[EpisodeRelease, SeasonRelease, None]:
    """
    Return the latest downloaded entity of a series, either season pack or episode

    :param Series series: Series object
    :param bool downloaded: Downloaded flag
    :param int season: Filter by season
    :return:
    """
    latest_ep = get_latest_episode_release(series, downloaded, season)
    latest_season = get_latest_season_pack_release(series, downloaded, season)

    if latest_season is None and latest_ep is None:
        return None
    return max(latest_season, latest_ep)


def new_eps_after(series: Series, since_ep: Episode, session: Session) -> Tuple[int, str]:
    """
    :param since_ep: Episode instance
    :return: Number of episodes since then
    """
    series_eps = session.query(Episode).join(Episode.series).filter(Series.id == series.id)
    if series.identified_by == 'ep':
        if since_ep.season is None or since_ep.number is None:
            logger.debug(
                'new_eps_after for `{}` falling back to timestamp because latest dl in non-ep format',
                series.name,
            )
            return series_eps.filter(Episode.first_seen > since_ep.first_seen).count(), 'eps'
        count = series_eps.filter(
            (Episode.identified_by == 'ep')
            & (
                ((Episode.season == since_ep.season) & (Episode.number > since_ep.number))
                | (Episode.season > since_ep.season)
            )
        ).count()
    elif series.identified_by == 'seq':
        count = series_eps.filter(Episode.number > since_ep.number).count()
    elif series.identified_by == 'id':
        count = series_eps.filter(Episode.first_seen > since_ep.first_seen).count()
    else:
        logger.debug('unsupported identified_by `{}`', series.identified_by)
        count = 0
    return count, 'eps'


def new_seasons_after(series: Series, since_season: Season, session: Session) -> Tuple[int, str]:
    series_seasons = session.query(Season).join(Season.series).filter(Season.id == series.id)
    return series_seasons.filter(Season.first_seen > since_season.first_seen).count(), 'seasons'


def new_entities_after(since_entity: Union[Season, Episode]) -> Tuple[int, str]:
    session = Session.object_session(since_entity)
    series = since_entity.series
    if since_entity.is_season:
        func = new_seasons_after
    else:
        func = new_eps_after
    return func(series, since_entity, session)


def set_series_begin(series: Series, ep_id: Union[str, int]) -> Tuple[str, str]:
    """
    Set beginning for series

    :param Series series: Series instance
    :param ep_id: Integer for sequence mode, SxxEyy for episodic and yyyy-mm-dd for date.
    :raises ValueError: If malformed ep_id or series in different mode
    :return: tuple containing identified_by and identity_type
    """
    # If identified_by is not explicitly specified, auto-detect it based on begin identifier
    # TODO: use some method of series parser to do the identifier parsing
    session = Session.object_session(series)
    identified_by, entity_type = parse_episode_identifier(ep_id, identify_season=True)
    if identified_by == 'ep':
        ep_id = ep_id.upper()
        if entity_type == 'season':
            ep_id += 'E01'
    if series.identified_by not in ['auto', '', None]:
        if identified_by != series.identified_by:
            raise ValueError(
                f'`begin` value `{ep_id}` does not match identifier type for identified_by `{series.identified_by}`'
            )
    series.identified_by = identified_by
    episode = (
        session.query(Episode)
        .filter(Episode.series_id == series.id)
        .filter(Episode.identified_by == series.identified_by)
        .filter(Episode.identifier == str(ep_id))
        .first()
    )
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
    return identified_by, entity_type


def remove_series(name: str, forget: bool = False) -> None:
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
                    for entity in s.episodes + s.seasons:
                        for release in entity.downloaded_releases:
                            downloaded_releases.append(release.title)
                session.delete(s)
            session.commit()
            logger.debug('Removed series `{}` from database.', name)
        else:
            raise ValueError('Unknown series `%s`' % name)
    for downloaded_release in downloaded_releases:
        fire_event('forget', downloaded_release)


def remove_series_entity(name: str, identifier: str, forget: bool = False) -> None:
    """
    Remove all entities by `identifier` from series `name` from database.

    :param name: Name of series to be removed
    :param identifier: Series identifier to be deleted,
    :param forget: Indication whether or not to fire a 'forget' event
    """
    downloaded_releases = []
    with Session() as session:
        series = session.query(Series).filter(Series.name == name).first()
        if not series:
            raise ValueError('Unknown series `%s`' % name)

        def remove_entity(entity):
            if not series.begin:
                series.identified_by = (
                    ''  # reset identified_by flag so that it will be recalculated
                )
            session.delete(entity)
            logger.debug('Entity `{}` from series `{}` removed from database.', identifier, name)
            return [release.title for release in entity.downloaded_releases]

        name_to_parse = f'{series.name} {identifier}'
        parsed = plugin.get('parsing', 'series.db').parse_series(name_to_parse, name=series.name)
        if not parsed.valid:
            raise ValueError(f'Invalid identifier for series `{series.name}`: `{identifier}`')

        removed = False
        if parsed.season_pack:
            season = (
                session.query(Season)
                .filter(Season.season == parsed.season)
                .filter(Season.series_id == series.id)
                .first()
            )
            if season:
                removed = True
                downloaded_releases = remove_entity(season)
        else:
            episode = session.query(Episode).filter(Episode.series_id == series.id)
            if parsed.episode:
                episode = episode.filter(Episode.number == parsed.episode).filter(
                    Episode.season == parsed.season
                )
            else:
                episode = episode.filter(Episode.identifier == parsed.identifier)
            episode = episode.first()
            if episode:
                removed = True
                downloaded_releases = remove_entity(episode)
        if not removed:
            raise ValueError(f'Unknown identifier `{identifier}` for series `{name.capitalize()}`')

    if forget:
        for downloaded_release in downloaded_releases:
            fire_event('forget', downloaded_release)


def delete_episode_release_by_id(release_id: int) -> None:
    with Session() as session:
        release = session.query(EpisodeRelease).filter(EpisodeRelease.id == release_id).first()
        if release:
            session.delete(release)
            session.commit()
            logger.debug('Deleted release ID `{}`', release_id)
        else:
            raise ValueError('Unknown identifier `%s` for release' % release_id)


def delete_season_release_by_id(release_id: int) -> None:
    with Session() as session:
        release = session.query(SeasonRelease).filter(SeasonRelease.id == release_id).first()
        if release:
            session.delete(release)
            session.commit()
            logger.debug('Deleted release ID `{}`', release_id)
        else:
            raise ValueError('Unknown identifier `%s` for release' % release_id)


def shows_by_name(normalized_name: str, session: Session = None) -> List[Series]:
    """Returns all series matching `normalized_name`"""
    return (
        session.query(Series)
        .filter(Series._name_normalized.contains(normalized_name))
        .order_by(func.char_length(Series.name))
        .all()
    )


def shows_by_exact_name(normalized_name: str, session: Session = None) -> List[Series]:
    """Returns all series matching `normalized_name`"""
    return (
        session.query(Series)
        .filter(Series._name_normalized == normalized_name)
        .order_by(func.char_length(Series.name))
        .all()
    )


def show_by_id(show_id: int, session: Session = None) -> Series:
    """Return an instance of a show by querying its ID"""
    return session.query(Series).filter(Series.id == show_id).one()


def season_by_id(season_id: int, session: Session = None) -> Season:
    """Return an instance of an season by querying its ID"""
    return session.query(Season).filter(Season.id == season_id).one()


def episode_by_id(episode_id: int, session: Session = None) -> Episode:
    """Return an instance of an episode by querying its ID"""
    return session.query(Episode).filter(Episode.id == episode_id).one()


def episode_release_by_id(release_id: int, session: Session = None) -> EpisodeRelease:
    """Return an instance of an episode release by querying its ID"""
    return session.query(EpisodeRelease).filter(EpisodeRelease.id == release_id).one()


def season_release_by_id(release_id: int, session: Session = None) -> SeasonRelease:
    """Return an instance of an episode release by querying its ID"""
    return session.query(SeasonRelease).filter(SeasonRelease.id == release_id).one()


def show_episodes(
    series: Series,
    start: int = None,
    stop: int = None,
    count: bool = False,
    descending: bool = False,
    session: Session = None,
) -> Union[int, List[Episode]]:
    """Return all episodes of a given series"""
    episodes = session.query(Episode).filter(Episode.series_id == series.id)
    if count:
        return episodes.count()
    # Query episodes in sane order instead of iterating from series.episodes
    if series.identified_by == 'sequence':
        episodes = (
            episodes.order_by(Episode.number.desc())
            if descending
            else episodes.order_by(Episode.number)
        )
    elif series.identified_by == 'ep':
        episodes = (
            episodes.order_by(Episode.season.desc(), Episode.number.desc())
            if descending
            else episodes.order_by(Episode.season, Episode.number)
        )
    else:
        episodes = (
            episodes.order_by(Episode.identifier.desc())
            if descending
            else episodes.order_by(Episode.identifier)
        )
    return episodes.slice(start, stop).from_self().all()


def store_parser(
    session: Session, parser: 'SeriesParseResult', series: Series = None, quality: 'Quality' = None
) -> List[Union[SeasonRelease, EpisodeRelease]]:
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
        series = (
            session.query(Series)
            .filter(Series.name == parser.name)
            .filter(Series.id != None)
            .first()
        )
        if not series:
            logger.debug('adding series `{}` into db', parser.name)
            series = Series()
            series.name = parser.name
            session.add(series)
            logger.debug('-> added `{}`', series)

    releases = []
    for ix, identifier in enumerate(parser.identifiers):
        if parser.season_pack:
            # Checks if season object exist
            season = (
                session.query(Season)
                .filter(Season.season == parser.season)
                .filter(Season.series_id == series.id)
                .filter(Season.identifier == identifier)
                .first()
            )
            if not season:
                logger.debug('adding season `{}` into series `{}`', identifier, parser.name)
                season = Season()
                season.identifier = identifier
                season.identified_by = parser.id_type
                season.season = parser.season
                series.seasons.append(season)
                logger.debug('-> added season `{}`', season)
            session.flush()

            # Sets the filter_by, and filter_id for later releases query
            filter_id = season.id
            table = SeasonRelease
            filter_by = table.season_id
            entity = season

        else:
            # if episode does not exist in series, add new
            episode = (
                session.query(Episode)
                .filter(Episode.series_id == series.id)
                .filter(Episode.identifier == identifier)
                .filter(Episode.series_id != None)
                .first()
            )
            if not episode:
                logger.debug('adding episode `{}` into series `{}`', identifier, parser.name)
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
                logger.debug('-> added `{}`', episode)
            session.flush()

            # Sets the filter_by, and filter_id for later releases query
            table = EpisodeRelease
            filter_by = table.episode_id
            filter_id = episode.id
            entity = episode

        # if release does not exists in episode or season, add new
        #
        # NOTE:
        #
        # filter(Release.episode_id != None) fixes weird bug where release had/has been added
        # to database but doesn't have episode_id, this causes all kinds of havoc with the plugin.
        # perhaps a bug in sqlalchemy?
        release = (
            session.query(table)
            .filter(filter_by == filter_id)
            .filter(table.title == parser.data)
            .filter(table.quality == quality)
            .filter(table.proper_count == parser.proper_count)
            .filter(filter_by != None)
            .first()
        )
        if not release:
            logger.debug('adding release `{}`', parser)
            release = table()
            release.quality = quality
            release.proper_count = parser.proper_count
            release.title = parser.data
            entity.releases.append(release)  # pylint:disable=E1103
            logger.debug('-> added `{}`', release)
        releases.append(release)
    session.flush()  # Make sure autonumber ids are populated
    return releases


def add_series_entity(
    session: Session, series: Series, identifier: str, quality: 'Quality' = None
) -> None:
    """
    Adds entity identified by `identifier` to series `name` in database.

    :param series: Series in database to add entity to.
    :param identifier: Series identifier to be added.
    :param quality: If supplied, this will override the quality from the series parser.
    """
    name_to_parse = f'{series.name} {identifier}'
    if quality:
        name_to_parse += f' {quality}'
    parsed = plugin.get('parsing', 'series.db').parse_series(name_to_parse, name=series.name)
    if not parsed.valid:
        raise ValueError(f'Invalid identifier for series `{series.name}`: `{identifier}`.')

    added = store_parser(session, parsed, series=series)
    if not added:
        raise ValueError(f'Unable to add `{identifier}` to series `{series.name.capitalize()}`.')
    else:
        for release in added:
            release.downloaded = True
        logger.debug('Entity `{}` from series `{}` added to database.', identifier, series.name)
