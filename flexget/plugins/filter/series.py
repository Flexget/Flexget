import logging
import re
import time
from copy import copy
from datetime import datetime, timedelta
from sqlalchemy import (Column, Integer, String, Unicode, DateTime, Boolean,
                        desc, select, update, ForeignKey, Index, func)
from sqlalchemy.orm import relation, join
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.exc import OperationalError
from flexget import schema
from flexget.event import event
from flexget.utils import qualities
from flexget.utils.log import log_once
from flexget.utils.titles import SeriesParser, ParseWarning
from flexget.utils.sqlalchemy_utils import table_columns, table_exists, drop_tables, table_schema, table_add_column
from flexget.utils.tools import merge_dict_from_to, parse_timedelta
from flexget.utils.database import quality_property
from flexget.manager import Session
from flexget.plugin import (register_plugin, register_parser_option, get_plugin_by_name, get_plugin_keywords,
    PluginWarning, DependencyError, priority)

SCHEMA_VER = 4

log = logging.getLogger('series')
Base = schema.versioned_base('series', SCHEMA_VER)


@schema.upgrade('series')
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
        if not 'proper_count' in columns:
            log.info('Upgrading episode_releases table to have proper_count column')
            table_add_column('episode_releases', 'proper_count', Integer, session)
            release_table = table_schema('episode_releases', session)
            for row in session.execute(select([release_table.c.id, release_table.c.title])):
                # Recalculate the proper_count from title for old episodes
                proper_count = len([part for part in re.split('[\W_]+', row['title'].lower())
                                    if part in SeriesParser.propers])
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
        release_table = table_schema('episode_releases', session)
        log.info('Creating index on episode_releases table.')
        Index('ix_episode_releases_episode_id', release_table.c.episode_id).create(bind=session.bind)
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
        Index('ix_series_name_lower', series_table.c.name_lower).create(bind=session.bind)
        # Fill in lower case name column
        session.execute(update(series_table, values={'name_lower': func.lower(series_table.c.name)}))
        ver = 4

    return ver


@event('manager.db_cleanup')
def db_cleanup(session):
    # Clean up old undownloaded releases
    result = session.query(Release).filter(Release.downloaded == False).\
                                    filter(Release.first_seen < datetime.now() - timedelta(days=120)).delete()
    if result:
        log.verbose('Removed %d undownloaded episode releases.' % result)
    # Clean up episodes without releases
    result = session.query(Episode).filter(~Episode.releases.any()).delete(False)
    if result:
        log.verbose('Removed %d episodes without releases.' % result)
    # Clean up series without episodes
    result = session.query(Series).filter(~Series.episodes.any()).delete(False)
    if result:
        log.verbose('Removed %d series without episodes.' % result)


@event('manager.startup')
def repair(manager):
    """Perform database repairing and upgrading at startup."""
    if not manager.persist.get('series_repaired', False):
        session = Session()
        # For some reason at least I have some releases in database which don't belong to any episode.
        for release in session.query(Release).filter(Release.episode == None).all():
            log.info('Purging orphan release %s from database' % release.title)
            session.delete(release)
        session.commit()
        manager.persist['series_repaired'] = True


class LowerComparator(Comparator):
    def operate(self, op, other):
        return op(self.__clause_element__(), func.lower(other))


class Series(Base):

    """ Name is handled case insensitively transparently
    """

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    _name = Column('name', Unicode)
    _name_lower = Column('name_lower', Unicode, index=True)
    identified_by = Column(String)
    episodes = relation('Episode', backref='series', cascade='all, delete, delete-orphan')

    # Make a special property that does indexed case insensitive lookups on name, but stores/returns specified case
    def name_getter(self):
        return self._name

    def name_setter(self, value):
        self._name = value
        self._name_lower = value.lower()

    def name_comparator(self):
        return LowerComparator(self._name_lower)

    name = hybrid_property(name_getter, name_setter)
    name.comparator(name_comparator)

    def __repr__(self):
        return '<Series(id=%s,name=%s)>' % (self.id, self.name)


class Episode(Base):

    __tablename__ = 'series_episodes'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)

    season = Column(Integer)
    number = Column(Integer)

    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    releases = relation('Release', backref='episode', cascade='all, delete, delete-orphan')

    @property
    def first_seen(self):
        return min(release.first_seen for release in self.releases)

    @property
    def age(self):
        """
        :return: Pretty string representing age of episode. eg "23d 12h" or "No releases seen"
        """
        if not self.first_seen:
            return 'No releases seen'
        diff = datetime.now() - self.first_seen
        age_days = diff.days
        age_hours = diff.seconds / 60 / 60
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

    def __repr__(self):
        return '<Episode(id=%s,identifier=%s)>' % (self.id, self.identifier)

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

    def __repr__(self):
        return '<Release(id=%s,quality=%s,downloaded=%s,proper_count=%s,title=%s)>' % \
            (self.id, self.quality, self.downloaded, self.proper_count, self.title)


class SeriesDatabase(object):

    """Provides API to series database"""

    def get_first_seen(self, session, parser, min_qual=None, max_qual=None):
        """Return datetime when this episode of series was first seen"""
        release = session.query(Release.first_seen).join(Episode, Series).\
            filter(Series.name == parser.name).\
            filter(Episode.identifier == parser.identifier)
        if min_qual:
            release = release.filter(Release.quality >= min_qual)
        if max_qual:
            release = release.filter(Release.quality <= max_qual)
        release = release.order_by(Release.first_seen).first()
        if not release:
            log.trace('%s not seen, return current time' % parser)
            return datetime.now()
        return release[0]

    def get_latest_info(self, session, name):
        """Return latest known identifier in dict (season, episode, name) for series name"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Episode.season != None).\
            filter(Series.name == name).\
            order_by(desc(Episode.season)).\
            order_by(desc(Episode.number)).first()
        if not episode:
            # log.trace('get_latest_info: no info available for %s' % name)
            return False
        # log.trace('get_latest_info, series: %s season: %s episode: %s' % \
        #    (name, episode.season, episode.number))
        return {'season': episode.season, 'episode': episode.number, 'name': name}

    def auto_identified_by(self, session, name):
        """
        Determine if series :name: should be considered identified by episode or id format

        Returns 'ep' or 'id' if 3 of the first 5 were parsed as such. Returns 'ep' in the event of a tie.
        Returns 'auto' if there is not enough history to determine the format yet
        """
        total = session.query(Release).join(Episode, Series).\
            filter(Series.name == name).count()
        episodic = session.query(Release).join(Episode, Series).\
            filter(Series.name == name).\
            filter(Episode.season != None).\
            filter(Episode.number != None).count()
        non_episodic = total - episodic
        log.debug('series %s auto ep/id check: %s/%s' % (name, episodic, non_episodic))
        # Best of 5, episodic wins in a tie
        if episodic >= 3 and episodic >= non_episodic:
            return 'ep'
        elif non_episodic >= 3 and non_episodic > episodic:
            return 'id'
        else:
            return 'auto'

    def get_latest_download(self, session, name):
        """Return latest downloaded episode (season, episode, name) for series :name:"""
        latest_download = session.query(Episode).join(Release, Series).\
            filter(Series.name == name).\
            filter(Release.downloaded == True).\
            filter(Episode.season != None).\
            filter(Episode.number != None).\
            order_by(desc(Episode.season), desc(Episode.number)).first()

        if not latest_download:
            log.debug('get_latest_download returning false, no downloaded episodes found for: %s' % name)
            return False

        return {'season': latest_download.season, 'episode': latest_download.number, 'name': name}

    def get_downloaded(self, session, name, identifier):
        """Return list of downloaded releases for this episode"""
        downloaded = session.query(Release).join(Episode, Series).\
            filter(Series.name == name).\
            filter(Episode.identifier == identifier).\
            filter(Release.downloaded == True).all()
        if not downloaded:
            log.debug('get_downloaded: no %s downloads recorded for %s' % (identifier, name))
        return downloaded

    def store(self, session, parser):
        """Push series information into database. Returns added/existing release."""
        # if series does not exist in database, add new
        series = session.query(Series).\
            filter(Series.name == parser.name).\
            filter(Series.id != None).first()
        if not series:
            log.debug('adding series %s into db' % parser.name)
            series = Series()
            series.name = parser.name
            session.add(series)
            log.debug('-> added %s' % series)

        # if episode does not exist in series, add new
        episode = session.query(Episode).filter(Episode.series_id == series.id).\
            filter(Episode.identifier == parser.identifier).\
            filter(Episode.series_id != None).first()
        if not episode:
            log.debug('adding episode %s into series %s' % (parser.identifier, parser.name))
            episode = Episode()
            episode.identifier = parser.identifier
            # if episodic format
            if parser.season and parser.episode is not None:
                episode.season = parser.season
                episode.number = parser.episode
            series.episodes.append(episode)  # pylint:disable=E1103
            log.debug('-> added %s' % episode)

        # if release does not exists in episodes, add new
        #
        # NOTE:
        #
        # filter(Release.episode_id != None) fixes weird bug where release had/has been added
        # to database but doesn't have episode_id, this causes all kinds of havoc with the plugin.
        # perhaps a bug in sqlalchemy?
        release = session.query(Release).filter(Release.episode_id == episode.id).\
            filter(Release.quality == parser.quality).\
            filter(Release.proper_count == parser.proper_count).\
            filter(Release.episode_id != None).first()
        if not release:
            log.debug('adding release %s into episode' % parser)
            release = Release()
            release.quality = parser.quality
            release.proper_count = parser.proper_count
            release.title = parser.data
            episode.releases.append(release)  # pylint:disable=E1103
            log.debug('-> added %s' % release)
        return release


def forget_series(name):
    """Remove a whole series `name` from database."""
    session = Session()
    series = session.query(Series).filter(Series.name == name).first()
    if series:
        session.delete(series)
        session.commit()
        log.debug('Removed series %s from database.' % name)
    else:
        raise ValueError('Unknown series %s' % name)


def forget_series_episode(name, identifier):
    """Remove all episodes by `identifier` from series `name` from database."""
    session = Session()
    series = session.query(Series).filter(Series.name == name).first()
    if series:
        episode = session.query(Episode).filter(Episode.identifier == identifier).\
            filter(Episode.series_id == series.id).first()
        if episode:
            series.identified_by = ''  # reset identified_by flag so that it will be recalculated
            session.delete(episode)
            session.commit()
            log.debug('Episode %s from series %s removed from database.' % (identifier, name))
        else:
            raise ValueError('Unknown identifier %s for series %s' % (identifier, name.capitalize()))
    else:
        raise ValueError('Unknown series %s' % name)


class FilterSeriesBase(object):
    """
    Class that contains helper methods for both filter.series as well as plugins that configure it,
    such as all_series, series_premiere and import_series.
    """

    def build_options_validator(self, options):
        quals = [q.name for q in qualities.all()]
        options.accept('text', key='path')
        # set
        options.accept('dict', key='set').accept_any_key('any')
        # regexes can be given in as a single string ..
        options.accept('regexp', key='name_regexp')
        options.accept('regexp', key='ep_regexp')
        options.accept('regexp', key='id_regexp')
        # .. or as list containing strings
        options.accept('list', key='name_regexp').accept('regexp')
        options.accept('list', key='ep_regexp').accept('regexp')
        options.accept('list', key='id_regexp').accept('regexp')
        # quality
        options.accept('choice', key='quality').accept_choices(quals, ignore_case=True)
        options.accept('list', key='qualities').accept('choice').accept_choices(quals, ignore_case=True)
        options.accept('boolean', key='upgrade')
        options.accept('choice', key='min_quality').accept_choices(quals, ignore_case=True)
        options.accept('choice', key='max_quality').accept_choices(quals, ignore_case=True)
        # propers
        options.accept('boolean', key='propers')
        message = "should be in format 'x (minutes|hours|days|weeks)' e.g. '5 days'"
        options.accept('interval', key='propers', message=message + ' or yes/no')
        # expect flags
        options.accept('choice', key='identified_by').accept_choices(['ep', 'id', 'auto'])
        # timeframe
        options.accept('interval', key='timeframe', message=message)
        # strict naming
        options.accept('boolean', key='exact')
        # watched in SXXEXX form
        watched = options.accept('regexp_match', key='watched')
        watched.accept('(?i)s\d\de\d\d$', message='Must be in SXXEXX format')
        # watched in dict form
        watched = options.accept('dict', key='watched')
        watched.accept('integer', key='season')
        watched.accept('integer', key='episode')
        # from group
        options.accept('text', key='from_group')
        options.accept('list', key='from_group').accept('text')
        # parse only
        options.accept('boolean', key='parse_only')
        # This is a flag set by all_series and series_premiere plugins, it should not be set by the user
        options.accept('boolean', key='series_guessed')

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
            # if group name is known quality, convenience create settings with that quality
            if isinstance(group_name, basestring) and group_name.lower() in qualities.registry:
                config['settings'].setdefault(group_name, {}).setdefault('quality', group_name)
            for series in config[group_name]:
                # convert into dict-form if necessary
                series_settings = {}
                group_settings = config['settings'].get(group_name, {})
                if isinstance(series, dict):
                    series, series_settings = series.items()[0]
                    if series_settings is None:
                        raise Exception('Series %s has unexpected \':\'' % series)
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
                # Add quality: 720p if timeframe is specified with no quality
                if 'timeframe' in series_settings:
                    series_settings.setdefault('quality', '720p')

                group_series.append({series: series_settings})
            config[group_name] = group_series
        del config['settings']
        return config

    def prepare_config(self, config):
        """Generate a list of unique series from configuration.
        This way we don't need to handle two different configuration formats in the logic.
        Applies group settings with advanced form."""

        config = self.apply_group_options(config)
        return self.combine_series_lists(*config.values())

    def combine_series_lists(self, *series_lists, **kwargs):
        """Combines the series from multiple lists, making sure there are no doubles.

        If keyword argument log_once is set to True, an error message will be printed if a series
        is listed more than once, otherwise log_once will be used."""
        unique_series = {}
        for series_list in series_lists:
            for series in series_list:
                series, series_settings = series.items()[0]
                if series not in unique_series:
                    unique_series[series] = series_settings
                else:
                    if kwargs.get('log_once'):
                        log_once('Series %s is already configured in series plugin' % series, log)
                    else:
                        log.warning('Series %s is configured multiple times in series plugin.' % series)
                    # Combine the config dicts for both instances of the show
                    unique_series[series].update(series_settings)
        # Turn our all_series dict back into a list
        return [{series: settings} for (series, settings) in unique_series.iteritems()]

    def merge_config(self, feed, config):
        """Merges another series config dict in with the current one."""

        # Make sure we start with both configs as a list of complex series
        native_series = self.prepare_config(feed.config.get('series', {}))
        merging_series = self.prepare_config(config)
        feed.config['series'] = self.combine_series_lists(native_series, merging_series, log_once=True)
        return feed.config['series']


class FilterSeries(SeriesDatabase, FilterSeriesBase):
    """
    Intelligent filter for tv-series.

    http://flexget.com/wiki/Plugins/series
    """

    def __init__(self):
        self.parser2entry = {}
        self.backlog = None

    def on_process_start(self, feed):
        try:
            self.backlog = get_plugin_by_name('backlog').instance
        except DependencyError:
            log.warning('Unable utilize backlog plugin, episodes may slip trough timeframe')

    def validator(self):
        from flexget import validator

        def build_list(series):
            """Build series list to series."""
            series.accept('text')
            series.accept('number')
            bundle = series.accept('dict')
            # prevent invalid indentation level
            bundle.reject_keys(['set', 'path', 'timeframe', 'name_regexp',
                'ep_regexp', 'id_regexp', 'watched', 'quality', 'min_quality',
                'max_quality', 'qualities', 'exact', 'from_group'],
                'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
            bundle.accept_any_key('path')
            options = bundle.accept_any_key('dict')
            self.build_options_validator(options)

        root = validator.factory()

        # simple format:
        #   - series
        #   - another series

        simple = root.accept('list')
        build_list(simple)

        # advanced format:
        #   settings:
        #     group: {...}
        #   group:
        #     {...}

        advanced = root.accept('dict')
        settings = advanced.accept('dict', key='settings')
        settings.reject_keys(get_plugin_keywords())
        settings_group = settings.accept_any_key('dict')
        self.build_options_validator(settings_group)

        group = advanced.accept_any_key('list')
        build_list(group)

        return root

    def auto_exact(self, config):
        """Automatically enable exact naming option for series that look like a problem"""

        # generate list of all series in one dict
        all_series = {}
        for series_item in config:
            series_name, series_config = series_item.items()[0]
            all_series[series_name] = series_config

        # scan for problematic names, enable exact mode for them
        for series_name, series_config in all_series.iteritems():
            for name in all_series.keys():
                if (name.lower().startswith(series_name.lower())) and \
                   (name.lower() != series_name.lower()):
                    if not 'exact' in series_config:
                        log.verbose('Auto enabling exact matching for series %s (reason %s)' % (series_name, name))
                        series_config['exact'] = True

    def on_feed_start(self, feed):
        # ensure clean state
        self.parser2entry = {}

    # Run after metainfo_quality and before metainfo_series
    @priority(125)
    def on_feed_metainfo(self, feed):
        config = self.prepare_config(feed.config.get('series', {}))
        self.auto_exact(config)
        for series_item in config:
            series_name, series_config = series_item.items()[0]
            log.trace('series_name: %s series_config: %s' % (series_name, series_config))
            start_time = time.clock()
            self.parse_series(feed.session, feed.entries, series_name, series_config)
            took = time.clock() - start_time
            log.trace('parsing %s took %s' % (series_name, took))

    def on_feed_filter(self, feed):
        """Filter series"""
        # Parsing was done in metainfo phase, create the dicts to pass to process_series from the feed entries
        # key: series episode identifier ie. S01E02
        # value: seriesparser
        found_series = {}
        guessed_series = {}
        for entry in feed.entries:
            if entry.get('series_name') and entry.get('series_id') and entry.get('series_parser'):
                self.parser2entry[entry['series_parser']] = entry
                target = guessed_series if entry.get('series_guessed') else found_series
                target.setdefault(entry['series_name'], {}).setdefault(entry['series_id'], []).append(entry['series_parser'])

        config = self.prepare_config(feed.config.get('series', {}))

        for series_item in config:
            series_name, series_config = series_item.items()[0]
            if series_config.get('parse_only'):
                log.debug('Skipping filtering of series %s because of parse_only' % series_name)
                continue
            # yaml loads ascii only as str
            series_name = unicode(series_name)
            # Update database with capitalization from config
            feed.session.query(Series).filter(Series.name == series_name).\
                update({'name': series_name}, 'fetch')
            source = guessed_series if series_config.get('series_guessed') else found_series
            # If we didn't find any episodes for this series, continue
            if not source.get(series_name):
                log.trace('No entries found for %s this run.' % series_name)
                continue
            for id, eps in source[series_name].iteritems():
                for parser in eps:
                    # store found episodes into database and save reference for later use
                    release = self.store(feed.session, parser)
                    entry = self.parser2entry[parser]
                    entry['series_release'] = release

                    # set custom download path
                    if 'path' in series_config:
                        log.debug('setting %s custom path to %s' % (entry['title'], series_config.get('path')))
                        # Just add this to the 'set' dictionary, so that string replacement is done cleanly
                        series_config.setdefault('set', {}).update(path=series_config['path'])

                    # accept info from set: and place into the entry
                    if 'set' in series_config:
                        set = get_plugin_by_name('set')
                        set.instance.modify(entry, series_config.get('set'))

            log.trace('series_name: %s series_config: %s' % (series_name, series_config))

            import time
            start_time = time.clock()

            self.process_series(feed, source[series_name], series_name, series_config)

            took = time.clock() - start_time
            log.trace('processing %s took %s' % (series_name, took))

    def parse_series(self, session, entries, series_name, config):
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
        series = session.query(Series).filter(Series.name == series_name).first()
        if series:
            # configuration always overrides everything
            if 'identified_by' in config:
                series.identified_by = config['identified_by']
            # if series doesn't have identified_by flag already set, calculate one now
            if not series.identified_by or series.identified_by == 'auto':
                series.identified_by = self.auto_identified_by(session, series_name)
                log.debug('identified_by set to \'%s\' based on series history' % series.identified_by)
            # set flag from database
            identified_by = series.identified_by

        parser = SeriesParser(name=series_name,
                              identified_by=identified_by,
                              name_regexps=get_as_array(config, 'name_regexp'),
                              ep_regexps=get_as_array(config, 'ep_regexp'),
                              id_regexps=get_as_array(config, 'id_regexp'),
                              strict_name=config.get('exact', False),
                              allow_groups=get_as_array(config, 'from_group'))

        for entry in entries:
            # skip processed entries
            if entry.get('series_parser') and entry['series_parser'].valid and not entry.get('series_guessed') and \
               entry['series_parser'].name.lower() != series_name.lower():
                continue
            # scan from fields
            for field in ('title', 'description'):
                data = entry.get(field)
                # skip invalid fields
                if not isinstance(data, basestring) or not data:
                    continue
                # in case quality will not be found from title, set it from entry['quality'] if available
                quality = None
                if entry.get('quality', qualities.UNKNOWN) > qualities.UNKNOWN:
                    log.trace('Setting quality %s from entry field to parser' % entry['quality'])
                    quality = entry['quality']
                try:
                    parser.parse(data, field=field, quality=quality)
                except ParseWarning, pw:
                    log_once(pw.value, logger=log)

                if parser.valid:
                    break
            else:
                continue  # next field

            log.debug('%s detected as %s, field: %s' % (entry['title'], parser, parser.field))
            entry['series_parser'] = copy(parser)
            # add series, season and episode to entry
            entry['series_name'] = series_name
            entry['series_guessed'] = config.get('series_guessed', False)
            if 'quality' in entry and entry['quality'] != parser.quality:
                log.warning('Found different quality for %s. Was %s, overriding with %s.' % \
                    (entry['title'], entry['quality'], parser.quality))
            entry['quality'] = parser.quality
            entry['proper'] = parser.proper
            entry['proper_count'] = parser.proper_count
            if parser.season and parser.episode is not None:
                entry['series_season'] = parser.season
                entry['series_episode'] = parser.episode
            else:
                entry['series_season'] = time.gmtime().tm_year
            entry['series_id'] = parser.identifier

    def process_series(self, feed, series, series_name, config):
        """
        Accept or Reject episode from available releases, or postpone choosing.

        :param feed: Current Feed
        :param series: List of SeriesParser instances (?)
        :param series_name: Name of series being processed
        :param config: Series configuration
        """

        for eps in series.itervalues():
            if not eps:
                continue

            # sort episodes in order of quality
            eps.sort(reverse=True)

            log.debug('start with episodes: %s' % [e.data for e in eps])

            # reject episodes that have been marked as watched in config file
            if 'watched' in config:
                log.debug('-' * 20 + ' watched -->')
                if self.process_watched(feed, config, eps):
                    continue

            # proper handling
            log.debug('-' * 20 + ' process_propers -->')
            eps = self.process_propers(feed, config, eps)
            if not eps:
                continue

            log.debug('current episodes: %s' % [e.data for e in eps])

            # min_ and max_quality
            if 'min_quality' in config or 'max_quality' in config:
                eps = self.process_min_max_quality(config, eps)
                if not eps:
                    continue

            # qualities
            if 'qualities' in config or config.get('upgrade'):
                log.debug('-' * 20 + ' process_qualities -->')
                if self.process_qualities(feed, config, eps):
                    continue
                else:
                    # We haven't gotten any of our qualities, check timeframe to see
                    # if we should remove the requirement
                    if self.process_timeframe(feed, config, eps, series_name):
                        continue

            # reject downloaded
            log.debug('-' * 20 + ' downloaded -->')
            if self.process_downloaded(feed, eps):
                continue

            best = eps[0]
            log.debug('continuing w. episodes: %s' % [e.data for e in eps])
            log.debug('best episode is: %s' % best.data)

            # episode advancement. used only with season based series
            # We check if they are integers so that if season/episode is 0 this isn't skipped.
            if isinstance(best.season, int) and isinstance(best.episode, int):
                if feed.manager.options.disable_advancement:
                    log.debug('episode advancement disabled')
                else:
                    log.debug('-' * 20 + ' episode advancement -->')
                    if self.process_episode_advancement(feed, eps, series):
                        continue

            # quality
            if 'quality' in config:
                if self.process_quality(feed, config, eps):
                    continue
                else:
                    # We didn't make a quality match, check timeframe to see
                    # if we should remove the requirement
                    if self.process_timeframe(feed, config, eps, series_name):
                        continue

            # All the remaining match requirements, just choose the best
            reason = 'only matching choice'
            if len(eps) > 1:
                reason = 'choosing best remaining'
            feed.accept(self.parser2entry[eps[0]], reason)

    def process_propers(self, feed, config, eps):
        """
        Accepts needed propers. Nukes episodes from which there exists proper.

        :returns: A list of episodes to continue processing.
        """
        # Return if there are no propers for this episode
        if not any(ep.proper_count > 0 for ep in eps):
            return eps

        pass_filter = []
        best_propers = []
        # Since eps is sorted by quality then proper_count we always see the highest proper for a quality first.
        (last_qual, best_proper) = (None, 0)
        for ep in eps:
            if not ep.quality == last_qual:
                last_qual, best_proper = ep.quality, ep.proper_count
                if ep.proper_count > 0:
                    best_propers.append(ep)
            if ep.proper_count < best_proper:
                # nuke qualities which there is a better proper available
                feed.reject(self.parser2entry[ep], 'nuked')
            else:
                pass_filter.append(ep)

        # If propers support is turned off, or proper timeframe has expired just return the filtered eps list
        if 'propers' in config:
            if isinstance(config['propers'], bool):
                if not config['propers']:
                    return pass_filter
            else:
                # propers with timeframe
                log.debug('proper timeframe: %s' % config['propers'])
                try:
                    timeframe = parse_timedelta(config['propers'])
                except ValueError:
                    raise PluginWarning('Invalid time format', log)

                first_seen = self.get_first_seen(feed.session, eps[0])
                expires = first_seen + timeframe
                log.debug('propers timeframe: %s' % timeframe)
                log.debug('first_seen: %s' % first_seen)
                log.debug('propers ignore after: %s' % str(expires))

                if datetime.now() > expires:
                    log.debug('propers timeframe expired')
                    return pass_filter

        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        downloaded_qualities = [d.quality for d in downloaded_releases]

        log.debug('downloaded qualities: %s' % downloaded_qualities)

        def proper_downloaded(parser):
            for release in downloaded_releases:
                if release.quality == parser.quality and release.proper_count >= parser.proper_count:
                    return True

        # Accept propers we actually need, and remove them from the list of entries to continue processing
        for ep in best_propers:
            if ep.quality in downloaded_qualities and not proper_downloaded(ep):
                feed.accept(self.parser2entry[ep], 'proper')
                pass_filter.remove(ep)

        return pass_filter

    def process_downloaded(self, feed, eps):
        """
        Rejects all episodes (regardless of quality) if this episode has been downloaded.

        :returns: True when episode has already been downloaded
        """
        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        log.debug('downloaded: %s' % [e.title for e in downloaded_releases])
        if downloaded_releases and eps:
            log.debug('identifier %s is downloaded' % eps[0].identifier)
            for ep in eps:
                # Reject these episodes
                feed.reject(self.parser2entry[ep], 'already downloaded episode with id `%s`' % ep.identifier)
            return True

    def process_quality(self, feed, config, eps):
        """
        Accepts first episode matching the quality configured for the series.

        :return: True if accepted something
        """
        quality = qualities.get(config['quality'])
        # scan for quality
        for ep in eps:
            if quality == ep.quality:
                entry = self.parser2entry[ep]
                log.debug('Series accepting. %s meets quality %s' % (entry['title'], quality))
                feed.accept(self.parser2entry[ep], 'quality met')
                return True

    def process_min_max_quality(self, config, eps):
        """
        Filters eps that do not fall between min_quality and max_quality.

        :returns: A list of eps that are in the acceptable range
        """
        min = qualities.get(config.get('min_quality', ''), qualities.UNKNOWN)
        max = qualities.get(config.get('max_quality', ''), qualities.max())
        log.debug('min: %s max: %s' % (min, max))
        result = []
        # see if any of the eps match accepted qualities
        for ep in eps:
            quality = ep.quality
            log.debug('ep: %s min: %s max: %s' % (ep.data, min.value, max.value,))
            if quality <= max and quality >= min:
                result.append(ep)
        if not result:
            log.debug('no quality meets requirements')
        return result

    def process_watched(self, feed, config, eps):
        """
        Rejects all episodes older than defined in watched.

        :returns: True when rejected because of watched
        """
        from sys import maxint
        best = eps[0]
        wconfig = config.get('watched')
        season = wconfig.get('season', -1)
        episode = wconfig.get('episode', maxint)
        if best.season < season or (best.season == season and best.episode <= episode):
            log.debug('%s episode %s is already watched, rejecting all occurrences' % (best.name, best.identifier))
            for ep in eps:
                entry = self.parser2entry[ep]
                feed.reject(entry, 'watched')
            return True

    def process_episode_advancement(self, feed, eps, series):
        """Rejects all episodes that are too old or new (advancement), return True when this happens."""

        current = eps[0]
        latest = self.get_latest_download(feed.session, current.name)
        log.debug('latest download: %s' % latest)
        log.debug('current: %s' % current)

        if latest:
            # allow few episodes "backwards" in case of missed eps
            grace = len(series) + 2
            if (current.season < latest['season']) or (current.season == latest['season'] and current.episode < (latest['episode'] - grace)):
                log.debug('too old! rejecting all occurrences')
                for ep in eps:
                    feed.reject(self.parser2entry[ep], 'Too much in the past from latest downloaded episode S%02dE%02d' %
                        (latest['season'], latest['episode']))
                return True

            if current.season > latest['season'] + 1:
                log.debug('too new! rejecting all occurrences')
                for ep in eps:
                    feed.reject(self.parser2entry[ep],
                        ('Too much in the future from latest downloaded episode S%02dE%02d. '
                         'See `--disable-advancement` if this should be downloaded.') %
                        (latest['season'], latest['episode']))
                return True

    def process_timeframe(self, feed, config, eps, series_name):
        """
        Runs the timeframe logic to determine if we should wait for a better quality.
        Saves current best to backlog if timeframe has not expired.

        :returns: True - if we should keep the quality (or qualities) restriction
                  False - if the quality restriction should be released, due to timeframe expiring
        """

        if 'timeframe' not in config:
            return True

        best = eps[0]

        # parse options
        log.debug('timeframe: %s' % config['timeframe'])
        try:
            timeframe = parse_timedelta(config['timeframe'])
        except ValueError:
            raise PluginWarning('Invalid time format', log)

        # Make sure we only start timing from the first seen quality that matches min and max requirements.
        min_quality = config.get('min_quality') and qualities.get(config['min_quality'])
        max_quality = config.get('max_quality') and qualities.get(config['max_quality'])
        first_seen = self.get_first_seen(feed.session, best, min_quality, max_quality)
        expires = first_seen + timeframe
        log.debug('timeframe: %s, first_seen: %s, expires: %s' % (timeframe, first_seen, expires))

        stop = feed.manager.options.stop_waiting.lower() == series_name.lower()
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

            entry = self.parser2entry[best]
            log.info('Timeframe waiting %s for %sh:%smin, currently best is %s' % \
                (series_name, hours, minutes, entry['title']))

            # add best entry to backlog (backlog is able to handle duplicate adds)
            if self.backlog:
                self.backlog.add_backlog(feed, entry)
            return True

    def process_qualities(self, feed, config, eps):
        """
        Handles all modes that can accept more than one quality per episode. (qualities, upgrade)

        :returns: True - if at least one wanted quality has been downloaded or accepted.
                  False - if no wanted qualities have been accepted
        """

        # Get list of already downloaded qualities
        downloaded_qualities = [r.quality for r in self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)]
        log.debug('downloaded_qualities: %s' % downloaded_qualities)

        # If quality is configured, make sure it is defined in wanted qualities
        if config.get('quality'):
            config.setdefault('qualities', []).append(config['quality'])
        # If qualities key is configured, we only want qualities defined in it.
        wanted_qualities = set([qualities.get(name) for name in config.get('qualities', [])])
        log.debug('Wanted qualities: %s' % wanted_qualities)

        def wanted(quality):
            """Returns True if we want this quality based on the config options."""
            wanted = not wanted_qualities or quality in wanted_qualities
            if config.get('upgrade'):
                wanted = wanted and quality > max(downloaded_qualities or [qualities.UNKNOWN])
            return wanted

        for ep in eps:
            log.debug('ep: %s quality: %s' % (ep.data, ep.quality))
            if not wanted(ep.quality):
                log.debug('%s is unwanted quality' % ep.quality)
                continue
            if ep.quality in downloaded_qualities:
                feed.reject(self.parser2entry[ep], 'quality downloaded')
            else:
                feed.accept(self.parser2entry[ep], 'quality wanted')
                downloaded_qualities.append(ep.quality)  # don't accept more of these
        return bool(downloaded_qualities)

    def on_feed_exit(self, feed):
        """Learn succeeded episodes"""
        log.debug('on_feed_exit')
        for entry in feed.accepted:
            if 'series_release' in entry:
                log.debug('marking %s as downloaded' % entry['series_release'])
                entry['series_release'].downloaded = True
            else:
                log.debug('%s is not a series' % entry['title'])
        # clear feed state
        self.parser2entry = {}


# Register plugin
register_plugin(FilterSeries, 'series')
register_parser_option('--stop-waiting', action='store', dest='stop_waiting', default='',
                       metavar='NAME', help='Stop timeframe for a given series.')
register_parser_option('--disable-advancement', action='store_true', dest='disable_advancement', default=False,
                       help='Disable episode advancement for this run.')
