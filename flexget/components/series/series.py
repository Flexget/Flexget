import argparse
import itertools
import sys
import time
from collections import defaultdict
from copy import copy
from datetime import datetime
from typing import List, Union

from loguru import logger
from sqlalchemy import not_
from sqlalchemy.orm import joinedload, object_session

from flexget import options, plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.manager import Session
from flexget.utils import qualities
from flexget.utils.log import log_once
from flexget.utils.tools import chunked, get_config_as_array, merge_dict_from_to, parse_timedelta

from . import db
from .utils import normalize_series_name

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.parsing.parsers import parser_common as plugin_parser_common
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='parsers')

logger = logger.bind(name='series')

try:
    preferred_clock = time.process_time
except AttributeError:
    preferred_clock = time.clock


@event('manager.lock_acquired')
def repair(manager):
    # Perform database repairing and upgrading at startup.
    if not manager.persist.get('series_repaired', False):
        session = Session()
        try:
            # For some reason at least I have some releases in database which don't belong to any episode.
            for release in (
                session.query(db.EpisodeRelease).filter(db.EpisodeRelease.episode == None).all()
            ):
                logger.info('Purging orphan release {} from database', release.title)
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
        removed_tasks = session.query(db.SeriesTask)
        if manager.tasks:
            removed_tasks = removed_tasks.filter(not_(db.SeriesTask.name.in_(manager.tasks)))
        deleted = removed_tasks.delete(synchronize_session=False)
        if deleted:
            session.commit()


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
        logger.verbose(
            'Found different quality for `{}`. Was `{}`, overriding with `{}`.',
            entry['title'],
            entry['quality'],
            parser.quality,
        )
    entry['quality'] = parser.quality
    entry['proper'] = parser.proper
    entry['proper_count'] = parser.proper_count
    entry['release_group'] = parser.group
    entry['season_pack'] = parser.season_pack
    if parser.id_type == 'ep':
        entry['series_season'] = parser.season
        if not parser.season_pack:
            entry['series_episode'] = parser.episode
    elif parser.id_type == 'date':
        entry['series_date'] = parser.id
        entry['series_season'] = parser.id.year
    else:
        entry['series_season'] = time.gmtime().tm_year
    entry['series_episodes'] = parser.episodes
    entry['series_id'] = parser.pack_identifier
    entry['series_id_type'] = parser.id_type
    entry['series_identified_by'] = parser.identified_by
    entry['series_exact'] = parser.strict_name

    # If a config is passed in, also look for 'path' and 'set' options to set more fields
    if config:
        # set custom download path
        if 'path' in config:
            logger.debug(
                'setting custom path for `{}` to `{}`', entry['title'], config.get('path')
            )
            # Just add this to the 'set' dictionary, so that string replacement is done cleanly
            config.setdefault('set', {}).update(path=config['path'])

        # accept info from set: and place into the entry
        if 'set' in config:
            plugin.get('set', 'series').modify(entry, config.get('set'))


class FilterSeriesBase:
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
                'qualities': {
                    'type': 'array',
                    'items': {'type': 'string', 'format': 'quality_requirements'},
                },
                'timeframe': {'type': 'string', 'format': 'interval'},
                'upgrade': {'type': 'boolean'},
                'target': {'type': 'string', 'format': 'quality_requirements'},
                # Specials
                'specials': {'type': 'boolean'},
                # Propers (can be boolean, or an interval string)
                'propers': {'type': ['boolean', 'string'], 'format': 'interval'},
                # Identified by
                'identified_by': {
                    'type': 'string',
                    'enum': ['ep', 'date', 'sequence', 'id', 'auto'],
                },
                # Strict naming
                'exact': {'type': 'boolean'},
                # Begin takes an ep, sequence or date identifier
                'begin': {'type': ['string', 'integer'], 'format': 'episode_or_season_id'},
                'from_group': one_or_more({'type': 'string'}),
                'parse_only': {'type': 'boolean'},
                'special_ids': one_or_more({'type': 'string'}),
                'prefer_specials': {'type': 'boolean'},
                'assume_special': {'type': 'boolean'},
                'tracking': {'type': ['boolean', 'string'], 'enum': [True, False, 'backfill']},
                # Season pack
                'season_packs': {
                    'oneOf': [
                        {'type': 'boolean'},
                        {'type': 'integer'},
                        {'type': 'string', 'enum': ['always', 'only']},
                        {
                            'type': 'object',
                            'properties': {
                                'threshold': {'type': 'integer', 'minimum': 0},
                                'reject_eps': {'type': 'boolean'},
                            },
                            'required': ['threshold', 'reject_eps'],
                            'additionalProperties': False,
                        },
                    ]
                },
            },
            'additionalProperties': False,
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

    def season_pack_opts(self, season_packs):
        """
        Parse the user's `season_packs` option, and turn it in to a more useful form.
        """
        if season_packs in [False, None]:
            return False
        opts = {'threshold': 0, 'reject_eps': False}
        if season_packs is True:
            return opts
        elif isinstance(season_packs, int):
            opts['threshold'] = season_packs
        elif isinstance(season_packs, str):
            if season_packs == 'always':
                opts['threshold'] = sys.maxsize
            else:  # 'only'
                opts['reject_eps'] = True
        elif isinstance(season_packs, dict):
            opts = season_packs
        return opts

    def apply_group_options(self, config):
        """Applies group settings to each item in series group and removes settings dict."""

        # Make sure config is in grouped format first
        config = self.make_grouped_config(config)
        for group_name in config:
            if group_name == 'settings':
                continue
            group_series = []
            if isinstance(group_name, str):
                # if group name is known quality, convenience create settings with that quality
                try:
                    qualities.Requirements(group_name)
                    config['settings'].setdefault(group_name, {}).setdefault('target', group_name)
                except ValueError:
                    # If group name is not a valid quality requirement string, do nothing.
                    pass
            group_settings = config['settings'].get(group_name, {})
            for series in config[group_name]:
                # convert into dict-form if necessary
                series_settings = {}
                if isinstance(series, dict):
                    series, series_settings = list(series.items())[0]
                # Make sure this isn't a series with no name
                if not series:
                    logger.warning('Series config contains a series with no name!')
                    continue
                # make sure series name is a string to accommodate for "24"
                if not isinstance(series, str):
                    series = str(series)
                # if series have given path instead of dict, convert it into a dict
                if isinstance(series_settings, str):
                    series_settings = {'path': series_settings}
                # merge group settings into this series settings
                merge_dict_from_to(group_settings, series_settings)
                # Convert to dict if watched is in SXXEXX format
                if isinstance(series_settings.get('watched'), str):
                    season, episode = series_settings['watched'].upper().split('E')
                    season = season.lstrip('S')
                    series_settings['watched'] = {'season': int(season), 'episode': int(episode)}
                # Convert enough to target for backwards compatibility
                if 'enough' in series_settings:
                    logger.warning(
                        'Series setting `enough` has been renamed to `target`. Please update your config.'
                    )
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
                        log_once(
                            'Series `%s` is already configured in series plugin' % series, logger
                        )
                    else:
                        logger.warning(
                            'Series `{}` is configured multiple times in series plugin.', series
                        )
                    # Combine the config dicts for both instances of the show
                    merge_dict_from_to(series_settings, unique_series[series])
        # Turn our all_series dict back into a list
        # sort by reverse alpha, so that in the event of 2 series with common prefix, more specific is parsed first
        return [{s: unique_series[s]} for s in sorted(unique_series, reverse=True)]

    def merge_config(self, task, config):
        """Merges another series config dict in with the current one."""

        # Make sure we start with both configs as a list of complex series
        native_series = self.prepare_config(task.config.get('series', {}))
        merging_series = self.prepare_config(config)
        task.config['series'] = self.combine_series_lists(
            native_series, merging_series, log_once=True
        )
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
                'additionalProperties': self.settings_schema,
            },
            # advanced format:
            #   settings:
            #     group: {...}
            #   group:
            #     {...}
            'properties': {
                'settings': {'type': 'object', 'additionalProperties': self.settings_schema}
            },
            'additionalProperties': {
                'type': 'array',
                'items': {
                    'type': ['string', 'number', 'object'],
                    'additionalProperties': self.settings_schema,
                },
            },
        }

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
                if (name.lower().startswith(series_name.lower())) and (
                    name.lower() != series_name.lower()
                ):
                    if 'exact' not in series_config:
                        logger.verbose(
                            'Auto enabling exact matching for series `{}` (reason: `{}`)',
                            series_name,
                            name,
                        )
                        series_config['exact'] = True

    # Run after metainfo_quality and before metainfo_series
    @plugin.priority(125)
    def on_task_metainfo(self, task, config):
        config = self.prepare_config(config)
        self.auto_exact(config)

        parser = plugin.get('parsing', self)

        start_time = preferred_clock()

        # Sort Entries into data model similar to https://en.wikipedia.org/wiki/Trie
        # Only process series if both the entry title and series title first letter match
        entries_map = defaultdict(list)
        for entry in task.entries:
            parsed = parser.parse_series(entry['title'])
            if parsed.name:
                entries_map[parsed.name[:1].lower()].append(entry)
            else:
                # If parsing failed, use first char of each word in the entry title
                for word in entry['title'].replace(' ', '.').split('.'):
                    entries_map[word[:1].lower()].append(entry)

        with Session() as session:
            # Preload series
            # str() added to make sure number shows (e.g. 24) are turned into strings

            # First add all series config names (normalized)
            series_names = [str(normalize_series_name(list(s.keys())[0])) for s in config]
            # Add series names from the config without normalization to capture configs
            #  that use slightly different series names. See https://github.com/Flexget/Flexget/issues/2057
            series_names.extend(
                str(list(s.keys())[0])
                for s in config
                if str(list(s.keys())[0]) not in series_names
            )

            existing_db_series = []

            for chunk in chunked(series_names):
                existing_db_series.extend(
                    session.query(db.Series).filter(db.Series.name.in_(chunk))
                )

            existing_db_series = {s.name_normalized: s for s in existing_db_series}

            for series_item in config:
                series_name, series_config = list(series_item.items())[0]
                alt_names = get_config_as_array(series_config, 'alternate_name')
                db_series = existing_db_series.get(normalize_series_name(series_name))
                db_identified_by = db_series.identified_by if db_series else None
                letters = set(
                    [series_name[:1].lower()]
                    + [normalize_series_name(series_name)[:1].lower()]
                    + [alt[:1].lower() for alt in alt_names]
                )
                entries = {entry for letter in letters for entry in entries_map.get(letter, [])}
                if entries:
                    self.parse_series(entries, series_name, series_config, db_identified_by)

        logger.debug('series on_task_metainfo took {} to parse', preferred_clock() - start_time)

    def on_task_filter(self, task, config):
        """Filter series"""
        # Parsing was done in metainfo phase, create the dicts to pass to process_series from the task entries
        # key: series episode identifier ie. S01E02
        # value: seriesparser

        config = self.prepare_config(config)
        found_series = {}
        for entry in task.entries:
            if (
                entry.get('series_name')
                and entry.get('series_id') is not None
                and entry.get('series_parser')
            ):
                found_series.setdefault(entry['series_name'], []).append(entry)

        # Prefetch series
        with Session() as session:
            # str() added to make sure number shows (e.g. 24) are turned into strings
            series_names = [str(list(s.keys())[0]) for s in config]
            existing_series = (
                session.query(db.Series)
                .filter(db.Series.name.in_(series_names))
                .options(joinedload('alternate_names'))
                .all()
            )
            existing_series_map = {s.name_normalized: s for s in existing_series}
            # Expunge so we can work on de-attached while processing the series to minimize db locks
            session.expunge_all()

        start_time = preferred_clock()
        for series_item in config:
            with Session() as session:
                series_name, series_config = list(series_item.items())[0]

                if series_config.get('parse_only'):
                    logger.debug(
                        'Skipping filtering of series `{}` because of parse_only', series_name
                    )
                    continue

                # Make sure number shows (e.g. 24) are turned into strings
                series_name = str(series_name)
                db_series = existing_series_map.get(normalize_series_name(series_name))
                if not db_series:
                    logger.debug('adding series `{}` into db', series_name)
                    db_series = db.Series()
                    db_series.name = series_name
                    db_series.identified_by = series_config.get('identified_by', 'auto')
                    session.add(db_series)
                    logger.debug('-> added `{}`', db_series)
                    session.flush()  # Flush to get an id on series before adding alternate names.
                    alts = series_config.get('alternate_name', [])
                    if not isinstance(alts, list):
                        alts = [alts]
                    for alt in alts:
                        db._add_alt_name(alt, db_series, series_name, session)
                    existing_series_map[db_series.name_normalized] = db_series
                else:
                    # Add existing series back to session
                    session.add(db_series)

                # Skip if series not within entries
                if series_name not in found_series:
                    continue

                series_entries = {}
                for entry in found_series[series_name]:
                    # store found episodes into database and save reference for later use
                    releases = db.store_parser(
                        session,
                        entry['series_parser'],
                        series=db_series,
                        quality=entry.get('quality'),
                    )
                    entry['series_releases'] = [r.id for r in releases]
                    if hasattr(releases[0], 'episode'):
                        entity = releases[0].episode
                    else:
                        entity = releases[0].season
                    series_entries.setdefault(entity, []).append(entry)

                # If we didn't find any episodes for this series, continue
                if not series_entries:
                    logger.trace('No entries found for `{}` this run.', series_name)
                    continue

                # configuration always overrides everything
                if series_config.get('identified_by', 'auto') != 'auto':
                    db_series.identified_by = series_config['identified_by']
                # if series doesn't have identified_by flag already set, calculate one now that new eps are added to db
                if not db_series.identified_by or db_series.identified_by == 'auto':
                    db_series.identified_by = db.auto_identified_by(db_series)
                    logger.debug(
                        'identified_by set to `{}` based on series history',
                        db_series.identified_by,
                    )
                # Remove begin episode if identified_by has now been set to a different type than begin ep
                if (
                    db_series.begin
                    and db_series.identified_by != 'auto'
                    and db_series.identified_by != db_series.begin.identified_by
                ):
                    logger.warning(
                        f'Removing begin episode for {series_name} ({db_series.begin.identifier}) because '
                        f'it does not match the identified_by type for series ({db_series.identified_by})'
                    )
                    del db_series.begin

                self.process_series(task, series_entries, series_config)

        logger.debug('processing series took {}', preferred_clock() - start_time)

    def parse_series(self, entries, series_name, config, db_identified_by=None):
        """
        Search for `series_name` and populate all `series_*` fields in entries when successfully parsed

        :param entries: List of entries to process
        :param series_name: Series name which is being processed
        :param config: Series config being processed
        :param db_identified_by: Series config being processed
        """

        # set parser flags flags based on config / database
        identified_by = config.get('identified_by', 'auto')
        if identified_by == 'auto':
            # set flag from database
            identified_by = db_identified_by or 'auto'

        params = {
            'identified_by': identified_by,
            'alternate_names': get_config_as_array(config, 'alternate_name'),
            'name_regexps': get_config_as_array(config, 'name_regexp'),
            'strict_name': config.get('exact', False),
            'allow_groups': get_config_as_array(config, 'from_group'),
            'date_yearfirst': config.get('date_yearfirst'),
            'date_dayfirst': config.get('date_dayfirst'),
            'special_ids': get_config_as_array(config, 'special_ids'),
            'prefer_specials': config.get('prefer_specials'),
            'assume_special': config.get('assume_special'),
        }
        for id_type in plugin_parser_common.SERIES_ID_TYPES:
            params[id_type + '_regexps'] = get_config_as_array(config, id_type + '_regexp')

        parser = plugin.get('parsing', self)
        for entry in entries:
            # skip processed entries
            if (
                entry.get('series_parser')
                and entry['series_parser'].valid
                and entry['series_parser'].name.lower() != series_name.lower()
            ):
                continue

            # Quality field may have been manipulated by e.g. assume_quality. Use quality field from entry if available.
            parsed = parser.parse_series(entry['title'], name=series_name, **params)
            if not parsed.valid:
                continue
            parsed.field = 'title'

            logger.debug(
                '`{}` detected as `{}`, field: `{}`', entry['title'], parsed, parsed.field
            )
            populate_entry_fields(entry, parsed, config)

    def process_series(self, task, series_entries, config):
        """
        Accept or Reject episode or season pack from available releases, or postpone choosing.

        :param task: Current Task
        :param series_entries: dict mapping Episodes or Seasons to entries for that episode or season_pack
        :param config: Series configuration
        """
        accepted_seasons: List[int] = []

        def _exclude_season_on_accept(
            *args,
            series_entity: Union[db.Season, db.Episode],
            accepted_seasons_list: List[int],
            **kwargs,
        ) -> None:
            # need to reject all other episode/season packs for an accepted season during the task,
            # can't wait for task learn phase
            if series_entity.is_season:
                logger.debug(
                    'adding season number `{}` to accepted seasons for this task',
                    series_entity.season,
                )
                accepted_seasons_list.append(series_entity.season)

        # sort for season packs first, order by season number ascending. Uses -1 in case entity does not return a
        # season number or sort will crash
        for entity, entries in sorted(
            series_entries.items(), key=lambda e: (e[0].is_season, e[0].season or -1), reverse=True
        ):
            if not entries:
                continue

            # Add season exclude hook to all entries so it will get added to list in all code paths of entry acceptance
            for entry in entries:
                entry.add_hook(
                    action='accept',
                    func=_exclude_season_on_accept,
                    series_entity=entity,
                    accepted_seasons_list=accepted_seasons,
                )

            reason = None

            logger.debug('start with entities: {}', [e['title'] for e in entries])

            season_packs = self.season_pack_opts(config.get('season_packs', False))
            # reject season packs unless specified
            if entity.is_season and not season_packs:
                for entry in entries:
                    entry.reject('season pack support is turned off')
                continue

            # reject episodes if season pack is set to 'only'
            if not entity.is_season and season_packs and season_packs['reject_eps']:
                for entry in entries:
                    entry.reject('season pack only mode')
                continue

            # Determine episode threshold for season pack
            ep_threshold = season_packs['threshold'] if season_packs else 0

            # check that a season pack for this season wasn't already accepted in this task run
            if entity.season in accepted_seasons:
                for entry in entries:
                    entry.reject(
                        'already accepted season pack for season `%s` in this task' % entity.season
                    )
                continue

            # reject entity that have been marked as watched in config file
            if entity.series.begin:
                if entity < entity.series.begin:
                    for entry in entries:
                        entry.reject(
                            f'Entity `{entity.identifier}` is before begin value of `{entity.series.begin.identifier}`'
                        )
                    continue

            # skip special episodes if special handling has been turned off
            if not config.get('specials', True) and entity.identified_by == 'special':
                logger.debug('Skipping special episode as support is turned off.')
                continue

            logger.debug('current entities: {}', [e['title'] for e in entries])

            # quality filtering
            if 'quality' in config:
                entries = self.process_quality(config, entries)
                if not entries:
                    continue
                reason = 'matches quality'

            # Many of the following functions need to know this info. Only look it up once.
            downloaded = entity.downloaded_releases
            downloaded_qualities = [rls.quality for rls in downloaded]

            # proper handling
            logger.debug('-' * 20 + ' process_propers -->')
            entries = self.process_propers(config, entity, entries)
            if not entries:
                continue

            # Remove any eps we already have from the list
            for entry in reversed(
                entries
            ):  # Iterate in reverse so we can safely remove from the list while iterating
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
                    logger.debug('-' * 20 + ' process_qualities -->')
                    self.process_qualities(config, entries, downloaded)
                    continue
                elif config.get('upgrade'):
                    entries[0].accept('is an upgrade to existing quality')
                    continue

                # Reject entity because we have them
                for entry in entries:
                    entry.reject('entity has already been downloaded')
                continue

            best = entries[0]
            logger.debug('continuing w. entities: {}', [e['title'] for e in entries])
            logger.debug('best entity is: `{}`', best['title'])

            # episode tracking. used only with season and sequence based series
            if entity.identified_by in ['ep', 'sequence']:
                if task.options.disable_tracking or not config.get('tracking', True):
                    logger.debug('episode tracking disabled')
                else:
                    logger.debug('-' * 20 + ' tracking -->')
                    # Grace is number of distinct eps in the task for this series + 2
                    backfill = config.get('tracking') == 'backfill'
                    if self.process_entity_tracking(
                        entity,
                        entries,
                        grace=len(series_entries) + 2,
                        backfill=backfill,
                        threshold=ep_threshold,
                    ):
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
                    if self.process_timeframe(task, config, entity, entries):
                        continue
                    reason = 'Timeframe expired, choosing best available'
                else:
                    # If target or qualities is configured without timeframe, don't accept anything now
                    continue

            # Just pick the best ep if we get here
            reason = reason or 'choosing first acceptable match'
            best.accept(reason)

    def process_propers(self, config, episode, entries):
        """
        Accepts needed propers. Nukes episodes from which there exists proper.

        :returns: A list of episodes to continue processing.
        """

        pass_filter = []
        # First find best available proper for each quality without modifying incoming entry order
        sorted_entries = sorted(
            entries, key=lambda e: (e['quality'], e['proper_count']), reverse=True
        )
        best_propers = {
            q: next(e) for q, e in itertools.groupby(sorted_entries, key=lambda e: e['quality'])
        }
        for entry in entries:
            if entry['proper_count'] < best_propers[entry['quality']]['proper_count']:
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
            logger.debug('proper timeframe: {}', config['propers'])
            timeframe = parse_timedelta(config['propers'])

            first_seen = episode.first_seen
            expires = first_seen + timeframe
            logger.debug('propers timeframe: {}', timeframe)
            logger.debug('first_seen: {}', first_seen)
            logger.debug('propers ignore after: {}', expires)

            if datetime.now() > expires:
                logger.debug('propers timeframe expired')
                return pass_filter

        downloaded_qualities = {d.quality: d.proper_count for d in episode.downloaded_releases}
        logger.debug('propers - downloaded qualities: {}', downloaded_qualities)

        # Accept propers we actually need, and remove them from the list of entries to continue processing
        for quality, entry in best_propers.items():
            if (
                quality in downloaded_qualities
                and entry['proper_count'] > downloaded_qualities[quality]
            ):
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
                logger.debug('Target quality already achieved.')
                return True
        # scan for quality
        for entry in entries:
            if req.allows(entry['quality']):
                logger.debug(
                    'Accepted by series. `{}` meets quality requirement `{}`.', entry['title'], req
                )
                entry.accept('target quality')
                return True

    def process_quality(self, config, entries):
        """
        Filters eps that do not fall between within our defined quality standards.

        :returns: A list of eps that are in the acceptable range
        """
        reqs = qualities.Requirements(config['quality'])
        logger.debug('quality req: {}', reqs)
        result = []
        # see if any of the eps match accepted qualities
        for entry in entries:
            if reqs.allows(entry['quality']):
                result.append(entry)
            else:
                logger.verbose(
                    'Ignored `{}`. Does not meet quality requirement `{}`.', entry['title'], reqs
                )
        if not result:
            logger.debug('no quality meets requirements')
        return result

    def process_entity_tracking(self, entity, entries, grace, threshold, backfill=False):
        """
        Rejects all entity that are too old or new, return True when this happens.

        :param entity: Entity model
        :param list entries: List of entries for given episode.
        :param int grace: Number of episodes before or after latest download that are allowed.
        :param bool backfill: If this is True, previous episodes will be allowed,
            but forward advancement will still be restricted.
        """

        latest = db.get_latest_release(entity.series)
        if entity.series.begin and (not latest or entity.series.begin > latest):
            latest = entity.series.begin
        logger.debug('latest download: {}', latest)
        logger.debug('current: {}', entity)

        if latest:
            # reject any entity if a season pack for this season was already downloaded
            if entity.season in entity.series.completed_seasons:
                logger.debug('season `{}` already completed for this series', entity.season)
                for entry in entries:
                    entry.reject('season `%s` is already completed' % entity.season)
                return True

            # Test if episode threshold has been met
            if entity.is_season and entity.series.episodes_for_season(entity.season) > threshold:
                logger.debug('threshold of {} has been met, skipping season pack', threshold)
                for entry in entries:
                    entry.reject(
                        'The configured number of episodes for this season has already been downloaded'
                    )
                return True

            if latest.identified_by == entity.identified_by:
                # Allow any previous episodes this season, or previous episodes within grace if sequence
                if not backfill:
                    if entity.season < latest.season or (
                        entity.identified_by == 'sequence'
                        and entity.number < (latest.number - grace)
                    ):
                        logger.debug('too old! rejecting all occurrences')
                        for entry in entries:
                            entry.reject(
                                'Too much in the past from latest downloaded entity %s'
                                % latest.identifier
                            )
                        return True

                # Allow future episodes within grace, or first episode of next season, or season pack of next season
                if (
                    entity.season > latest.season + 1
                    or not entity.is_season
                    and (
                        (entity.season > latest.season and entity.number > 1)
                        or not latest.is_season
                        and (
                            entity.season == latest.season
                            and entity.number > (latest.number + grace)
                        )
                    )
                ):
                    logger.debug('too new! rejecting all occurrences')
                    for entry in entries:
                        entry.reject(
                            'Too much in the future from latest downloaded entity `%s`. '
                            'See `--disable-tracking` if this should be downloaded.'
                            % latest.identifier
                        )
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
        logger.debug('timeframe: {}', config['timeframe'])
        timeframe = parse_timedelta(config['timeframe'])

        if config.get('quality'):
            req = qualities.Requirements(config['quality'])
            seen_times = [rls.first_seen for rls in episode.releases if req.allows(rls.quality)]
        else:
            seen_times = [rls.first_seen for rls in episode.releases]
        # Somehow we can get here without having qualifying releases (#2779) make sure min doesn't crash
        first_seen = min(seen_times) if seen_times else datetime.now()
        expires = first_seen + timeframe
        logger.debug('timeframe: {}, first_seen: {}, expires: {}', timeframe, first_seen, expires)

        stop = normalize_series_name(task.options.stop_waiting) == episode.series._name_normalized
        if expires <= datetime.now() or stop:
            # Expire timeframe, accept anything
            logger.info('Timeframe expired, releasing quality restriction.')
            return False
        else:
            # verbose waiting, add to backlog
            diff = expires - datetime.now()

            hours, remainder = divmod(diff.seconds, 3600)
            hours += diff.days * 24
            minutes, _ = divmod(remainder, 60)

            logger.info(
                '`{}`: timeframe waiting for {:02d}h:{:02d}min. Currently best is `{}`.',
                episode.series.name,
                hours,
                minutes,
                best['title'],
            )

            # add best entry to backlog (backlog is able to handle duplicate adds)
            plugin.get('backlog', self).add_backlog(task, best, session=object_session(episode))

            return True

    def process_qualities(self, config, entries, downloaded):
        """
        Handles all modes that can accept more than one quality per episode. (qualities, upgrade)

        :returns: True - if at least one wanted quality has been downloaded or accepted.
                  False - if no wanted qualities have been accepted
        """

        # Get list of already downloaded qualities
        downloaded_qualities = [r.quality for r in downloaded]
        logger.debug('downloaded_qualities: {}', downloaded_qualities)

        # If qualities key is configured, we only want qualities defined in it.
        wanted_qualities = {qualities.Requirements(name) for name in config.get('qualities', [])}
        # Compute the requirements from our set that have not yet been fulfilled
        still_needed = [
            req
            for req in wanted_qualities
            if not any(req.allows(qual) for qual in downloaded_qualities)
        ]
        logger.debug('wanted qualities: {}', wanted_qualities)

        def wanted(quality):
            """Returns True if we want this quality based on the config options."""
            wanted_q = not wanted_qualities or any(req.allows(quality) for req in wanted_qualities)
            if config.get('upgrade'):
                wanted_q = wanted_q and quality > max(
                    downloaded_qualities or [qualities.Quality()]
                )
            return wanted_q

        for entry in entries:
            quality = entry['quality']
            logger.debug('ep: `{}`, quality: `{}`', entry['title'], quality)
            if not wanted(quality):
                logger.debug('`{}` is an unwanted quality', quality)
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
        logger.debug('on_task_learn')
        for entry in task.accepted:
            if 'series_releases' in entry:
                with Session() as session:
                    season_num = ep_num = 0
                    if entry['season_pack']:
                        season_num = (
                            session.query(db.SeasonRelease)
                            .filter(db.SeasonRelease.id.in_(entry['series_releases']))
                            .update({'downloaded': True}, synchronize_session=False)
                        )
                    else:
                        ep_num = (
                            session.query(db.EpisodeRelease)
                            .filter(db.EpisodeRelease.id.in_(entry['series_releases']))
                            .update({'downloaded': True}, synchronize_session=False)
                        )

                logger.debug(
                    'marking {} episode releases and {} season releases as downloaded for `{}`',
                    ep_num,
                    season_num,
                    entry,
                )
            else:
                logger.debug('`{}` is not a series', entry['title'])


class SeriesDBManager(FilterSeriesBase):
    """Update in the database with series info from the config"""

    @plugin.priority(0)
    def on_task_start(self, task, config):
        # Only operate if task changed
        if not task.config_modified:
            return

        # Clear all series from this task
        with Session() as session:
            add_series_tasks = {}

            session.query(db.SeriesTask).filter(db.SeriesTask.name == task.name).delete()
            if not task.config.get('series'):
                return
            config = self.prepare_config(task.config['series'])

            # Prefetch series
            names = [str(list(series.keys())[0]) for series in config]
            existing_series = (
                session.query(db.Series)
                .filter(db.Series.name.in_(names))
                .options(joinedload('alternate_names'))
                .all()
            )
            existing_series_map = {s.name_normalized: s for s in existing_series}

            for series_item in config:
                series_name, series_config = list(series_item.items())[0]
                # Make sure number shows (e.g. 24) are turned into strings
                series_name = str(series_name)
                db_series = existing_series_map.get(normalize_series_name(series_name))
                alts = series_config.get('alternate_name', [])
                if not isinstance(alts, list):
                    alts = [alts]
                if db_series:
                    # Update database with capitalization from config
                    db_series.name = series_name
                    # Remove the alternate names not present in current config
                    db_series.alternate_names = [
                        alt for alt in db_series.alternate_names if alt.alt_name in alts
                    ]
                    # Add/update the possibly new alternate names
                else:
                    logger.debug(
                        'adding series `{}` `{}` into db (on_task_start)',
                        series_name,
                        normalize_series_name(series_name),
                    )
                    logger.debug('adding series `{}` into db (on_task_start)', series_name)
                    db_series = db.Series()
                    db_series.name = series_name
                    session.add(db_series)
                    session.flush()  # flush to get id on series before creating alternate names
                    existing_series_map[db_series.name_normalized] = db_series
                    logger.debug('-> added `{}`', db_series)
                for alt in alts:
                    db._add_alt_name(alt, db_series, series_name, session)

                logger.debug('connecting series `{}` to task `{}`', db_series.name, task.name)

                # Add in bulk at the end
                if db_series.id not in add_series_tasks:
                    series_task = db.SeriesTask(task.name)
                    series_task.series_id = db_series.id
                    add_series_tasks[db_series.id] = series_task

                if series_config.get('identified_by', 'auto') != 'auto':
                    db_series.identified_by = series_config['identified_by']
                # Set the begin episode
                if series_config.get('begin'):
                    try:
                        db.set_series_begin(db_series, series_config['begin'])
                    except ValueError as e:
                        raise plugin.PluginError(e)

            if add_series_tasks:
                session.bulk_save_objects(add_series_tasks.values())


@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeries, 'series', api_ver=2)
    # This is a builtin so that it can update the database for tasks that may have had series plugin removed
    plugin.register(SeriesDBManager, 'series_db', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    exec_parser.add_argument(
        '--stop-waiting',
        action='store',
        dest='stop_waiting',
        default='',
        metavar='NAME',
        help='stop timeframe for a given series',
    )
    exec_parser.add_argument(
        '--disable-tracking',
        action='store_true',
        default=False,
        help='disable episode advancement for this run',
    )
    # Backwards compatibility
    exec_parser.add_argument(
        '--disable-advancement',
        action='store_true',
        dest='disable_tracking',
        help=argparse.SUPPRESS,
    )
