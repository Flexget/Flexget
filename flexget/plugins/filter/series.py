import logging
import re
from copy import copy
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Unicode, DateTime, Boolean, desc, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation, join, synonym
from flexget import schema
from flexget.utils.log import log_once
from flexget.event import event
from flexget.utils.titles import SeriesParser, ParseWarning
from flexget.utils import qualities
from flexget.utils.sqlalchemy_utils import table_columns, table_exists, drop_tables
from flexget.utils.tools import merge_dict_from_to
from flexget.manager import Session
from flexget.plugin import register_plugin, register_parser_option, get_plugin_by_name, get_plugin_keywords, \
    PluginWarning, PluginError, DependencyError, priority


log = logging.getLogger('series')
Base = schema.versioned_base('series', 0)


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
            log.info('Upgrading episode_release table to have proper_count column')
            session.execute('ALTER TABLE episode_releases ADD proper_count INTEGER DEFAULT NULL')
            for release in session.query(Release).all():
                release.proper_count = len([part for part in re.split('[\W_]+', release.title.lower())
                                            if part in SeriesParser.propers])
        ver = 0
    return ver


class Series(Base):

    __tablename__ = 'series'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    episodes = relation('Episode', backref='series', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<Series(id=%s,name=%s)>' % (self.id, self.name)


class Episode(Base):

    __tablename__ = 'series_episodes'

    id = Column(Integer, primary_key=True)
    identifier = Column(String)
    first_seen = Column(DateTime)

    season = Column(Integer)
    number = Column(Integer)

    series_id = Column(Integer, ForeignKey('series.id'), nullable=False)
    releases = relation('Release', backref='episode', cascade='all, delete, delete-orphan')

    @property
    def age(self):
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
        if self.season == 1 and self.number == 1:
            return 'Series Premiere'
        elif self.number == 1:
            return 'Season Premiere'
        return False

    def __init__(self):
        self.first_seen = datetime.now()

    def __repr__(self):
        return '<Episode(id=%s,identifier=%s)>' % (self.id, self.identifier)


class Release(Base):

    __tablename__ = 'episode_releases'

    id = Column(Integer, primary_key=True)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'), nullable=False)
    _quality = Column('quality', String)
    downloaded = Column(Boolean, default=False)
    proper_count = Column(Integer, default=0)
    title = Column(Unicode)

    def get_quality(self):
        return qualities.get(self._quality)

    def set_quality(self, value):
        self._quality = value.name

    quality = synonym('_quality', descriptor=property(get_quality, set_quality))

    @property
    def proper(self):
        # TODO: TEMP
        import warnings
        warnings.warn("accessing deprecated release.proper, use release.proper_count instead")
        return self.proper_count > 0

    def __repr__(self):
        return '<Release(id=%s,quality=%s,downloaded=%s,proper_count=%s,title=%s)>' % \
            (self.id, self.quality, self.downloaded, self.proper_count, self.title)


@event('manager.startup')
def repair(manager):
    """Perform database repairing and upgrading at startup."""
    session = Session()
    # For some reason at least I have some releases in database which don't belong to any episode.
    for release in session.query(Release).filter(Release.episode == None).all():
        log.info('Purging orphan release %s from database' % release.title)
        session.delete(release)
    session.commit()


class SeriesPlugin(object):

    """Database helpers"""

    def get_first_seen(self, session, parser):
        """Return datetime when this episode of series was first seen"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(func.lower(Series.name) == parser.name.lower()).\
            filter(Episode.identifier == parser.identifier).first()
        if not episode:
            log.debugall('%s not seen, return current time' % parser)
            return datetime.now()
        return episode.first_seen

    def get_latest_info(self, session, name):
        """Return latest known identifier in dict (season, episode, name) for series name"""
        episode = session.query(Episode).select_from(join(Episode, Series)).\
            filter(Episode.season != None).\
            filter(func.lower(Series.name) == name.lower()).\
            order_by(desc(Episode.season)).\
            order_by(desc(Episode.number)).first()
        if not episode:
            # log.debugall('get_latest_info: no info available for %s' % name)
            return False
        # log.debugall('get_latest_info, series: %s season: %s episode: %s' % \
        #    (name, episode.season, episode.number))
        return {'season': episode.season, 'episode': episode.number, 'name': name}

    def auto_identified_by(self, session, name):
        """
        Determine if series :name: should be considered identified by episode or id format

        Returns 'ep' or 'id' if 3 of the first 5 were parsed as such. Returns 'ep' in the event of a tie.
        Returns 'auto' if there is not enough history to determine the format yet
        """
        total = session.query(Release).join(Episode).join(Series).\
            filter(func.lower(Series.name) == name.lower()).count()
        episodic = session.query(Release).join(Episode).join(Series).\
            filter(func.lower(Series.name) == name.lower()).\
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
            filter(func.lower(Series.name) == name.lower()).\
            filter(Release.downloaded == True).\
            filter(Episode.season != None).\
            filter(Episode.number != None).\
            order_by(desc(Episode.season), desc(Episode.number)).first()

        if not latest_download:
            log.debug('get_latest_download returning false, no downloaded episodes found for: %s' % name)
            return False

        return {'season': latest_download.season, 'episode': latest_download.number, 'name': name}

    def get_releases(self, session, name, identifier):
        """Return all releases for series by identifier."""
        return session.query(Release).join(Episode, Series).\
            filter(func.lower(Series.name) == name.lower()).\
            filter(Episode.identifier == identifier).all()

    def get_downloaded(self, session, name, identifier):
        """Return list of downloaded releases for this episode"""
        downloaded = session.query(Release).join(Episode, Series).\
            filter(func.lower(Series.name) == name.lower()).\
            filter(Episode.identifier == identifier).\
            filter(Release.downloaded == True).all()
        if not downloaded:
            log.debug('get_downloaded: no %s downloads recorded for %s' % (identifier, name))
        return downloaded

    def store(self, session, parser):
        """Push series information into database. Returns added/existing release."""
        # if series does not exist in database, add new
        series = session.query(Series).\
            filter(func.lower(Series.name) == parser.name.lower()).\
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
            if parser.season and parser.episode:
                episode.season = parser.season
                episode.number = parser.episode
            series.episodes.append(episode) # pylint:disable=E1103
            log.debug('-> added %s' % episode)

        # if release does not exists in episodes, add new
        #
        # NOTE:
        #
        # filter(Release.episode_id != None) fixes weird bug where release had/has been added
        # to database but doesn't have episode_id, this causes all kinds of havoc with the plugin.
        # perhaps a bug in sqlalchemy?
        release = session.query(Release).filter(Release.episode_id == episode.id).\
            filter(Release.quality == parser.quality.name).\
            filter(Release.proper_count == parser.proper_count).\
            filter(Release.episode_id != None).first()
        if not release:
            log.debug('adding release %s into episode' % parser)
            release = Release()
            release.quality = parser.quality
            release.proper_count = parser.proper_count
            release.title = parser.data
            episode.releases.append(release) # pylint:disable=E1103
            log.debug('-> added %s' % release)
        return release


def forget_series(name):
    """Remove a whole series :name: from database."""
    session = Session()
    series = session.query(Series).filter(func.lower(Series.name) == name.lower()).first()
    if series:
        session.delete(series)
        session.commit()
        log.debug('Removed series %s from database.' % name)
    else:
        raise ValueError('Unknown series %s' % name)


def forget_series_episode(name, identifier):
    """Remove all episodes by :identifier: from series :name: from database."""
    session = Session()
    series = session.query(Series).filter(func.lower(Series.name) == name.lower()).first()
    if series:
        episode = session.query(Episode).filter(Episode.identifier == identifier).\
            filter(Episode.series_id == series.id).first()
        if episode:
            session.delete(episode)
            session.commit()
            log.debug('Episode %s from series %s removed from database.' % (identifier, name))
        else:
            raise ValueError('Unknown identifier %s for series %s' % (identifier, name.capitalize()))
    else:
        raise ValueError('Unknown series %s' % name)


class FilterSeriesBase(object):
    """Class that contains helper methods for both filter.series as well as plugins that configure it,
     such as thetvdb_favorites, all_series and series_premiere."""

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
        options.accept('choice', key='min_quality').accept_choices(quals, ignore_case=True)
        options.accept('choice', key='max_quality').accept_choices(quals, ignore_case=True)
        # propers
        options.accept('boolean', key='propers')
        message = "should be in format 'x (minutes|hours|days|weeks)' e.g. '5 days'"
        time_regexp = r'\d+ (minutes|hours|days|weeks)'
        options.accept('regexp_match', key='propers', message=message + ' or yes/no').accept(time_regexp)
        # expect flags
        options.accept('choice', key='identified_by').accept_choices(['ep', 'id', 'auto'])
        # timeframe
        options.accept('regexp_match', key='timeframe', message=message).accept(time_regexp)
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

    def make_grouped_config(self, config):
        """Turns a simple series list into grouped format with a settings dict"""
        if not isinstance(config, dict):
            # convert simplest configuration internally grouped format
            config = {'simple': config,
                      'settings': {}}
        else:
            # already in grouped format, just get settings from there
            if not 'settings' in config:
                config['settings'] = {}

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
                        log.error('Series %s is configured multiple times in series plugin.' % series)
        # Turn our all_series dict back into a list
        return [{series: settings} for (series, settings) in unique_series.iteritems()]

    def merge_config(self, feed, config):
        """Merges another series config dict in with the current one."""

        # Make sure we start with both configs as a list of complex series
        native_series = self.prepare_config(feed.config.get('series', {}))
        merging_series = self.prepare_config(config)
        feed.config['series'] = self.combine_series_lists(native_series, merging_series, log_once=True)
        return feed.config['series']


class FilterSeries(SeriesPlugin, FilterSeriesBase):
    """
        Intelligent filter for tv-series.

        http://flexget.com/wiki/FilterSeries
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
                        log.info('Auto enabling exact matching for series %s (reason %s)' % (series_name, name))
                        series_config['exact'] = True

    # Run after metainfo_quality and before metainfo_series
    @priority(125)
    def on_feed_metainfo(self, feed):
        config = self.prepare_config(feed.config.get('series', {}))
        self.auto_exact(config)
        for series_item in config:
            series_name, series_config = series_item.items()[0]
            # yaml loads ascii only as str
            series_name = unicode(series_name)
            log.debugall('series_name: %s series_config: %s' % (series_name, series_config))

            import time
            start_time = time.clock()

            self.parse_series(feed, series_name, series_config)
            took = time.clock() - start_time
            log.debugall('parsing %s took %s' % (series_name, took))

    def on_feed_filter(self, feed):
        """Filter series"""
        # Parsing was done in metainfo phase, create the dicts to pass to process_series from the feed entries
        # key: series (episode) identifier ie. S01E02
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
            db_series = feed.session.query(Series).filter(func.lower(Series.name) == series_name.lower()).first()
            if db_series:
                db_series.name = series_name
            source = guessed_series if series_config.get('series_guessed') else found_series
            # If we didn't find any episodes for this series, continue
            if not source.get(series_name):
                log.debugall('No entries found for %s this run.' % series_name)
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
                        entry['path'] = series_config.get('path') % entry

                    # accept info from set: and place into the entry
                    if 'set' in series_config:
                        set = get_plugin_by_name('set')
                        set.instance.modify(entry, series_config.get('set'))

            log.debugall('series_name: %s series_config: %s' % (series_name, series_config))

            import time
            start_time = time.clock()

            self.process_series(feed, source[series_name], series_name, series_config)

            took = time.clock() - start_time
            log.debugall('processing %s took %s' % (series_name, took))

    def parse_series(self, feed, series_name, config):
        """
            Search for :series_name: and populate all series_* fields in entries when successfully parsed
        """

        def get_as_array(config, key):
            """Return configuration key as array, even if given as a single string"""
            v = config.get(key, [])
            if isinstance(v, basestring):
                return [v]
            return v

        # expect flags

        identified_by = config.get('identified_by', 'auto')
        if identified_by not in ['ep', 'id', 'auto']:
            raise PluginError('Unknown identified_by value %s for the series %s' % (identified_by, series_name))

        if identified_by == 'auto':
            # determine if series is known to be in season, episode format or identified by id
            identified_by = self.auto_identified_by(feed.session, series_name)
            if identified_by != 'auto':
                log.debug('identified_by set to \'%s\' based on series history' % identified_by)

        parser = SeriesParser(name=series_name,
                              identified_by=identified_by,
                              name_regexps=get_as_array(config, 'name_regexp'),
                              ep_regexps=get_as_array(config, 'ep_regexp'),
                              id_regexps=get_as_array(config, 'id_regexp'),
                              strict_name=config.get('exact', False),
                              allow_groups=get_as_array(config, 'from_group'))

        for entry in feed.entries:
            if entry.get('series_parser') and entry['series_parser'].valid and not entry.get('series_guessed') and \
               entry['series_parser'].name.lower() != series_name.lower():
                # This was detected as another series, we can skip it.
                continue
            else:
                for field in ['title', 'description']:
                    data = entry.get(field)
                    # skip invalid fields
                    if not isinstance(data, basestring) or not data:
                        continue
                    # in case quality will not be found from title, set it from entry['quality'] if available
                    quality = None
                    if entry.get('quality', qualities.UNKNOWN) > qualities.UNKNOWN:
                        log.debugall('Setting quality %s from entry field to parser' % entry['quality'])
                        quality = entry['quality']
                    try:
                        parser.parse(data, field=field, quality=quality)
                    except ParseWarning, pw:
                        from flexget.utils.log import log_once
                        log_once(pw.value, logger=log)

                    if parser.valid:
                        break
                else:
                    continue

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
            if parser.season and parser.episode:
                entry['series_season'] = parser.season
                entry['series_episode'] = parser.episode
            else:
                import time
                entry['series_season'] = time.gmtime().tm_year
            entry['series_id'] = parser.identifier

    def process_series(self, feed, series, series_name, config):
        """Accept or Reject episode from available releases, or postpone choosing."""
        for eps in series.itervalues():
            if not eps:
                continue
            whitelist = []

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
            removed, new_propers = self.process_propers(feed, config, eps)
            whitelist.extend(new_propers)

            # Remove the nuked eps
            for ep in removed:
                log.debug('removing nuked ep: %s' % ep)
                eps.remove(ep)

            if not eps:
                continue

            log.debug('current episodes: %s' % [e.data for e in eps])

            # qualities
            if 'qualities' in config:
                log.debug('-' * 20 + ' process_qualities -->')
                self.process_qualities(feed, config, eps, whitelist)
                continue

            # reject downloaded
            log.debug('-' * 20 + ' downloaded -->')
            for ep in self.process_downloaded(feed, eps, whitelist):
                feed.reject(self.parser2entry[ep], 'already downloaded episode with id \'%s\'' % str(ep.identifier))
                log.debug('downloaded removed: %s' % ep)
                eps.remove(ep)

            # no releases left, continue to next episode
            if not eps:
                continue

            best = eps[0]
            log.debug('continuing w. episodes: %s' % [e.data for e in eps])
            log.debug('best episode is: %s' % best.data)

            # episode advancement. used only with season based series
            if best.season and best.episode:
                if feed.manager.options.disable_advancement:
                    log.debug('episode advancement disabled')
                else:
                    log.debug('-' * 20 + ' episode advancement -->')
                    if self.process_episode_advancement(feed, eps, series):
                        continue

            # timeframe
            if 'timeframe' in config:
                log.debug('-' * 20 + ' timeframe -->')
                self.process_timeframe(feed, config, eps, series_name)
                continue

            # quality, min_quality, max_quality and NO timeframe
            if ('timeframe' not in config and 'qualities' not in config) and \
               ('quality' in config or 'min_quality' in config or 'max_quality' in config):
                log.debug('-' * 20 + ' process quality -->')
                self.process_quality(feed, config, eps)
                continue

            # no special configuration, just choose the best
            reason = 'only choice'
            if len(eps) > 1:
                reason = 'choose best'
            self.accept_series(feed, best, reason)

    def process_propers(self, feed, config, eps):
        """
            Accepts needed propers. Nukes episodes from which there exists proper.
            Returns a list of removed episodes.
        """

        proper_eps = [ep for ep in eps if ep.proper]
        # Return if there are no propers for this episode
        if not proper_eps:
            return [], []

        new_propers = {} # {quality: parser} format
        removed = []
        for ep in proper_eps:
            new_propers.setdefault(ep.quality, ep)
            if ep.quality not in new_propers or ep.proper_count > new_propers[ep.quality].proper_count:
                new_propers[ep.quality] = ep

        # nuke qualities which there is proper available
        for quality, proper_ep in new_propers.iteritems():
            for ep in set(eps) - set(removed):
                if ep.quality == quality and ep.proper_count < proper_ep.proper_count:
                    feed.reject(self.parser2entry[ep], 'nuked')
                    removed.append(ep)

        # If propers support is turned off, or proper timeframe has expired just return the nuked episodes
        if 'propers' in config:
            if isinstance(config['propers'], bool):
                if not config['propers']:
                    return removed, []
            else:
                # propers with timeframe
                amount, unit = config['propers'].split(' ')
                log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
                params = {unit: int(amount)}
                try:
                    timeframe = timedelta(**params)
                except TypeError:
                    raise PluginWarning('Invalid time format', log)

                first_seen = self.get_first_seen(feed.session, eps[0])
                expires = first_seen + timeframe
                log.debug('propers timeframe: %s' % timeframe)
                log.debug('first_seen: %s' % first_seen)
                log.debug('propers ignore after: %s' % str(expires))

                if datetime.now() > expires:
                    log.debug('propers timeframe expired')
                    return removed, []

        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        downloaded_qualities = [d.quality for d in downloaded_releases]

        log.debug('downloaded qualities: %s' % downloaded_qualities)

        def proper_downloaded(parser):
            for release in downloaded_releases:
                if release.quality == parser.quality and release.proper_count >= parser.proper_count:
                    return True

        # Make a list of propers we actually need
        needed_propers = []
        for quality, ep in new_propers.items():
            if quality in downloaded_qualities and not proper_downloaded(ep):
                needed_propers.append(ep)

        log.debug('needed new_propers: %s' % [e.data for e in needed_propers])
        for ep in needed_propers:
            feed.accept(self.parser2entry[ep], 'proper')

        return removed, needed_propers

    def process_downloaded(self, feed, eps, whitelist):
        """
            Rejects all downloaded episodes (regardless of quality).
            Doesn't reject reject anything in :whitelist:.
        """

        downloaded = set()
        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        log.debug('downloaded: %s' % [e.title for e in downloaded_releases])
        if downloaded_releases and eps:
            log.debug('identifier %s is downloaded' % eps[0].identifier)
            for ep in eps[:]:
                if ep not in whitelist:
                    # same episode can appear multiple times, so use a set to avoid duplicates
                    downloaded.add(ep)
        return downloaded

    def process_quality(self, feed, config, eps):
        """Accepts episodes that meet configured qualities"""

        min = qualities.UNKNOWN
        max = qualities.max()
        if 'quality' in config:
            quality = qualities.get(config['quality'])
            min, max = quality, quality
        else:
            min = qualities.get(config.get('min_quality', ''), min)
            max = qualities.get(config.get('max_quality', ''), max)
            log.debug('min: %s max: %s' % (min, max))
        # see if any of the eps match accepted qualities
        for ep in eps:
            quality = ep.quality
            log.debug('ep: %s min: %s max: %s quality: %r' % (ep.data, min.value, max.value, quality))
            if quality <= max and quality >= min:
                self.accept_series(feed, ep, 'meets quality')
                break
        else:
            log.debug('no quality meets requirements')

    def process_watched(self, feed, config, eps):
        """Rejects all episodes older than defined in watched, returns True when this happens."""

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
                    feed.reject(self.parser2entry[ep], 'too much in the past from latest downloaded episode S%02dE%02d' % (latest['season'], latest['episode']))
                return True

            if current.season > latest['season'] + 1:
                log.debug('too new! rejecting all occurrences')
                for ep in eps:
                    feed.reject(self.parser2entry[ep], 'too much in the future from latest downloaded episode S%02dE%02d' % (latest['season'], latest['episode']))
                return True

    def process_timeframe(self, feed, config, eps, series_name):
        """
            The nasty timeframe logic, too complex even to explain (for now).
            Returns True when there's no sense trying any other logic.
        """

        if 'max_quality' in config:
            log.warning('Timeframe does not support max_quality (yet)')
        if 'min_quality' in config:
            log.warning('Timeframe does not support min_quality (yet)')
        if 'qualities' in config:
            log.warning('Timeframe does not support qualities (yet)')

        best = eps[0]

        # parse options
        amount, unit = config['timeframe'].split(' ')
        log.debug('amount: %s unit: %s' % (repr(amount), repr(unit)))
        params = {unit: int(amount)}
        try:
            timeframe = timedelta(**params)
        except TypeError:
            raise PluginWarning('Invalid time format', log)

        quality_name = config.get('quality', '720p')
        if quality_name not in qualities.registry:
            log.error('Parameter quality has unknown value: %s' % quality_name)
        quality = qualities.get(quality_name)

        # scan for quality, starting from worst quality (reverse) (old logic, see note below)
        for ep in reversed(eps):
            if quality == ep.quality:
                entry = self.parser2entry[ep]
                log.debug('Timeframe accepting. %s meets quality %s' % (entry['title'], quality))
                self.accept_series(feed, ep, 'quality met, timeframe unnecessary')
                return True

        # expire timeframe, accept anything
        first_seen = self.get_first_seen(feed.session, best)
        expires = first_seen + timeframe
        log.debug('timeframe: %s' % timeframe)
        log.debug('first_seen: %s' % first_seen)
        log.debug('timeframe expires: %s' % str(expires))

        stop = feed.manager.options.stop_waiting.lower() == series_name.lower()
        if expires <= datetime.now() or stop:
            entry = self.parser2entry[best]
            if stop:
                log.info('Stopped timeframe, accepting %s' % (entry['title']))
            else:
                log.info('Timeframe expired, accepting %s' % (entry['title']))
            self.accept_series(feed, best, 'expired/stopped')
            for ep in eps:
                if ep == best:
                    continue
                entry = self.parser2entry[ep]
                feed.reject(entry, 'wrong quality')
            return True
        else:
            # verbose waiting, add to backlog
            diff = expires - datetime.now()

            hours, remainder = divmod(diff.seconds, 3600)
            hours += diff.days * 24
            minutes, seconds = divmod(remainder, 60)

            entry = self.parser2entry[best]
            log.info('Timeframe waiting %s for %sh:%smin, currently best is %s' % \
                (series_name, hours, minutes, entry['title']))

            # reject all episodes that are in timeframe
            log.debug('timeframe waiting %s episode %s, rejecting all occurrences' % (series_name, best.identifier))
            for ep in eps:
                feed.reject(self.parser2entry[ep], 'timeframe is waiting')
            # add best entry to backlog (backlog is able to handle duplicate adds)
            if self.backlog:
                self.backlog.add_backlog(feed, entry)
            return True

    # TODO: whitelist deprecated ?
    def process_qualities(self, feed, config, eps, whitelist=None):
        """
            Accepts all wanted qualities.
            Accepts whitelisted episodes even if downloaded.
        """

        # get list of downloaded releases
        downloaded_releases = self.get_downloaded(feed.session, eps[0].name, eps[0].identifier)
        log.debug('downloaded_releases: %s' % downloaded_releases)

        accepted_qualities = []

        def is_quality_downloaded(quality):
            if quality in accepted_qualities:
                return True
            for release in downloaded_releases:
                if release.quality == quality:
                    return True

        wanted_qualities = [qualities.get(name) for name in config['qualities']]
        log.debug('qualities: %s' % wanted_qualities)
        for ep in eps:
            log.debug('ep: %s quality: %s' % (ep.data, ep.quality))
            if ep.quality not in wanted_qualities:
                log.debug('%s is unwanted quality' % ep.quality)
                continue
            if is_quality_downloaded(ep.quality) and ep not in (whitelist or []):
                feed.reject(self.parser2entry[ep], 'quality downloaded')
            else:
                feed.accept(self.parser2entry[ep], 'quality wanted')
                accepted_qualities.append(ep.quality) # don't accept more of these

    # TODO: get rid of, see how feed.reject is called, consistency!
    def accept_series(self, feed, parser, reason):
        """Accept this series with a given reason"""
        entry = self.parser2entry[parser]
        if parser.field:
            if entry[parser.field] != parser.data:
                log.critical('BUG? accepted title is different from parser.data %s != %s, field=%s, series=%s' % \
                    (entry[parser.field], parser.data, parser.field, parser.name))
        feed.accept(entry, reason)

    def on_feed_exit(self, feed):
        """Learn succeeded episodes"""
        log.debug('on_feed_exit')
        for entry in feed.accepted:
            if 'series_release' in entry:
                log.debug('marking %s as downloaded' % entry['series_release'])
                entry['series_release'].downloaded = True
            else:
                log.debug('%s is not a series' % entry['title'])

# Register plugin

register_plugin(FilterSeries, 'series')
register_parser_option('--stop-waiting', action='store', dest='stop_waiting', default='',
                       metavar='NAME', help='Stop timeframe for a given series.')
register_parser_option('--disable-advancement', action='store_true', dest='disable_advancement', default=False,
                       help='Disable episode advancement for this run.')
