import contextlib
import itertools
import re

from loguru import logger
from sqlalchemy import desc

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.qualities import Quality, Requirements, _registry

from . import db

logger = logger.bind(name='next_series_episodes')

BACKFILL_LIMIT_DEFAULT = 25


class NextSeriesEpisodes:
    """Emit next episode number from all series configured in this task.

    Supports only 'ep' and 'sequence' mode series.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'from_start': {'type': 'boolean', 'default': False},
                    'backfill': {'type': 'boolean', 'default': False},
                    'backfill_limit': {
                        'type': 'integer',
                        'default': BACKFILL_LIMIT_DEFAULT,
                        'description': 'If the gap between episodes is larger than this limit, '
                        'they will not be emitted.',
                    },
                    'only_same_season': {'type': 'boolean', 'default': False},
                    'include_quality': {'type': 'boolean', 'default': True},
                },
                'additionalProperties': False,
            },
        ]
    }

    def __init__(self):
        self.rerun_entries = []
        self.series_settings = {}

    def _component_candidates(self, req_component) -> list[str] | None:
        """Return the concrete values a single requirement component allows, highest first.

        Handles bare values ("bluray"), pipe alternatives ("720p|1080p"), and
        min-max ranges ("720p-2160p") uniformly since all three enumerate to a
        finite set of literal values.

        :return: [] if unconstrained (contributes nothing to the search term), None if
            the requirement is an open-ended comparator (e.g. "<720p", "1080p+") or a
            "!" exclusion, neither of which can be written as a literal search term.
        """
        if req_component.acceptable:
            candidates = req_component.acceptable
        elif req_component.min and req_component.max:
            candidates = [
                comp
                for comp in _registry.values()
                if comp.type == req_component.type
                and req_component.min.value <= comp.value <= req_component.max.value
            ]
        elif req_component.min or req_component.max or req_component.none_of:
            return None
        else:
            return []
        return [comp.name for comp in sorted(candidates, key=lambda c: c.value, reverse=True)]

    def _extract_quality_strings(self, series_config: dict) -> list[str]:
        """Extract quality strings from series configuration for use in search queries.

        Resolution ranges ("720p-2160p") and alternatives on any component
        ("720p|1080p", "bluray|webdl") are expanded into every combination.
        Requirements that can't be expressed as literal search terms (e.g. "<=1080p",
        "!hdr") are skipped.

        :param series_config: Series configuration dict
        :return: List of quality strings, sorted highest first
        """
        quality_strings = []
        for key in ('qualities', 'target', 'quality'):
            value = series_config.get(key)
            if isinstance(value, list):
                quality_strings.extend(value)
            elif value:
                quality_strings.append(value)

        expanded_strings = []
        for q_str in quality_strings:
            try:
                req = Requirements(q_str)
            except ValueError:
                logger.debug('Invalid quality requirement string: {}', q_str)
                continue

            per_component_candidates = []
            for req_component in req.components:
                candidates = self._component_candidates(req_component)
                if candidates is None:
                    logger.debug(
                        'Skipping quality requirement not usable as search text: {}', q_str
                    )
                    break
                if candidates:
                    per_component_candidates.append(candidates)
            else:
                expanded_strings.extend(
                    ' '.join(combo) for combo in itertools.product(*per_component_candidates)
                )

        # Quality is directly sortable (highest first); dedupe while we're at it.
        return sorted(dict.fromkeys(expanded_strings), key=Quality, reverse=True)

    def ep_identifiers(self, season, episode):
        return [f'S{season:02d}E{episode:02d}', f'{season}x{episode:02d}']

    def sequence_identifiers(self, episode):
        # Use a set to remove doubles, which will happen depending on number of digits in episode
        return {f'{episode}', f'{episode:02d}', f'{episode:03d}'}

    def search_entry(self, series, season, episode, task, rerun=True):
        # Extract the alternate names for the series
        alts = [alt.alt_name for alt in series.alternate_names]
        # Also consider series name without parenthetical (year, country) an alternate name
        paren_match = re.match(r'(.+?)( \(.+\))?$', series.name)
        if paren_match.group(2):
            alts.append(paren_match.group(1))
        if series.identified_by == 'ep':
            search_strings = [f'{series.name} {id}' for id in self.ep_identifiers(season, episode)]
            series_id = f'S{season:02d}E{episode:02d}'
            for alt in alts:
                search_strings.extend([
                    f'{alt} {id}' for id in self.ep_identifiers(season, episode)
                ])
        else:
            search_strings = [f'{series.name} {id}' for id in self.sequence_identifiers(episode)]
            series_id = episode
            for alt in alts:
                search_strings.extend([f'{alt} {id}' for id in self.sequence_identifiers(episode)])

        # Append quality strings if include_quality option is enabled
        if self.config.get('include_quality'):
            series_config = self.series_settings.get(series.name)
            if series_config:
                quality_strings = self._extract_quality_strings(series_config)
                if quality_strings:
                    # For each quality (highest first), append all episode identifier variations
                    search_strings = [
                        f'{search_str} {quality_str}'
                        for quality_str in quality_strings
                        for search_str in search_strings
                    ]

        entry = Entry(
            title=search_strings[0],
            url='',
            search_strings=search_strings,
            series_name=series.name,
            series_alternate_names=alts,  # Not sure if this field is useful down the road.
            series_season=season,
            series_episode=episode,
            season_pack_lookup=False,
            series_id=series_id,
            series_id_type=series.identified_by,
        )
        if rerun:
            entry.on_complete(
                self.on_search_complete, task=task, identified_by=series.identified_by
            )
        return entry

    def on_task_input(self, task, config):
        if not config:
            return None
        if isinstance(config, bool):
            config = {}
        config.setdefault('backfill_limit', BACKFILL_LIMIT_DEFAULT)
        config.setdefault('include_quality', True)
        self.config = config
        if task.is_rerun:
            # Just return calculated next eps on reruns
            entries = self.rerun_entries
            self.rerun_entries = []
            return entries
        self.rerun_entries = []

        self.series_settings = {}
        if config.get('include_quality'):
            series_plugin = plugin.get('series', self)
            for series_item in series_plugin.prepare_config(task.config.get('series', {})):
                series_name, series_config = next(iter(series_item.items()))
                self.series_settings[series_name] = series_config

        entries = []
        impossible = {}
        with Session() as session:
            for seriestask in (
                session.query(db.SeriesTask).filter(db.SeriesTask.name == task.name).all()
            ):
                series = seriestask.series
                logger.trace('evaluating {}', series.name)
                if not series:
                    # TODO: How can this happen?
                    logger.debug('Found SeriesTask item without series specified. Cleaning up.')
                    session.delete(seriestask)
                    continue

                if series.identified_by not in ['ep', 'sequence']:
                    logger.trace('unsupported identified_by scheme')
                    reason = series.identified_by or 'auto'
                    impossible.setdefault(reason, []).append(series.name)
                    continue

                low_season = 0 if series.identified_by == 'ep' else -1
                # Don't look for seasons older than begin ep
                if series.begin and series.begin.season and series.begin.season > 1:
                    # begin-1 or the range() loop will never get to the begin season
                    low_season = max(series.begin.season - 1, 0)

                new_season = None
                check_downloaded = not config.get('backfill')
                latest_season = db.get_latest_release(series, downloaded=check_downloaded)
                if latest_season:
                    if latest_season.season <= low_season:
                        latest_season = new_season = low_season + 1
                    elif latest_season.season in series.completed_seasons:
                        latest_season = new_season = latest_season.season + 1
                    else:
                        latest_season = latest_season.season
                else:
                    latest_season = low_season + 1

                for season in range(latest_season, low_season, -1):
                    if season in series.completed_seasons:
                        logger.debug('season {} is marked as completed, skipping', season)
                        continue
                    logger.trace(
                        'Evaluating episodes for series {}, season {}', series.name, season
                    )
                    latest = db.get_latest_release(
                        series, season=season, downloaded=check_downloaded
                    )
                    if (
                        series.begin
                        and season == series.begin.season
                        and (not latest or latest < series.begin)
                    ):
                        # In case series.begin season is already completed, look in next available season
                        lookup_season = series.begin.season
                        ep_number = series.begin.number
                        while lookup_season in series.completed_seasons:
                            lookup_season += 1
                            # If season number was bumped, start looking for ep 1
                            ep_number = 1
                        entries.append(self.search_entry(series, lookup_season, ep_number, task))
                    elif latest and not config.get('backfill'):
                        entries.append(
                            self.search_entry(series, latest.season, latest.number + 1, task)
                        )
                    elif latest:
                        start_at_ep = 1
                        episodes_this_season = (
                            session
                            .query(db.Episode)
                            .filter(db.Episode.series_id == series.id)
                            .filter(db.Episode.season == season)
                        )
                        if series.identified_by == 'sequence':
                            # Don't look for missing too far back with sequence shows
                            start_at_ep = max(latest.number - 10, 1)
                            episodes_this_season = episodes_this_season.filter(
                                db.Episode.number >= start_at_ep
                            )
                        latest_ep_this_season = episodes_this_season.order_by(
                            desc(db.Episode.number)
                        ).first()
                        if latest_ep_this_season:
                            downloaded_this_season = (
                                episodes_this_season
                                .join(db.Episode.releases)
                                .filter(db.EpisodeRelease.downloaded)
                                .all()
                            )
                            # Calculate the episodes we still need to get from this season
                            if series.begin and series.begin.season == season:
                                start_at_ep = max(start_at_ep, series.begin.number)
                            eps_to_get = list(range(start_at_ep, latest_ep_this_season.number + 1))
                            for ep in downloaded_this_season:
                                with contextlib.suppress(ValueError):
                                    eps_to_get.remove(ep.number)
                            if len(eps_to_get) > config['backfill_limit']:
                                logger.warning(
                                    'Series {} has more than 50 episodes to backfill. Assuming this is an '
                                    'error and not searching for them.',
                                    series.name,
                                )
                            else:
                                entries.extend(
                                    self.search_entry(series, season, x, task, rerun=False)
                                    for x in eps_to_get
                                )
                            # If we have already downloaded the latest known episode, try the next episode
                            if latest_ep_this_season.releases:
                                entries.append(
                                    self.search_entry(
                                        series, season, latest_ep_this_season.number + 1, task
                                    )
                                )
                        else:
                            # No episode means that latest is a season pack, emit episode 1
                            entries.append(self.search_entry(series, season, 1, task))
                    # First iteration of a new season with no show begin and show has downloads
                    elif (
                        (new_season and season == new_season)
                        or config.get('from_start')
                        or config.get('backfill')
                    ):
                        entries.append(self.search_entry(series, season, 1, task))
                    else:
                        logger.verbose(
                            'Series `{}` has no history. Set begin option, or use CLI `series begin` '
                            'subcommand to set first episode to emit',
                            series.name,
                        )
                        break
                    # Skip older seasons if we are not in backfill mode
                    if not config.get('backfill'):
                        logger.debug('backfill is not enabled; skipping older seasons')
                        break

        for reason, series in impossible.items():
            logger.verbose(
                'Series `{}` with identified_by value `{}` are not supported. ',
                ', '.join(sorted(series)),
                reason,
            )

        return entries

    def on_search_complete(self, entry, task=None, identified_by=None, **kwargs):
        """Decides whether we should look for next ep/season based on whether we found/accepted any episodes."""
        with Session() as session:
            series = (
                session.query(db.Series).filter(db.Series.name == entry['series_name']).first()
            )
            latest = db.get_latest_release(series)
            db_release = (
                session
                .query(db.EpisodeRelease)
                .join(db.EpisodeRelease.episode)
                .join(db.Episode.series)
                .filter(db.Series.name == entry['series_name'])
                .filter(db.Episode.season == entry['series_season'])
                .filter(db.Episode.number == entry['series_episode'])
                .first()
            )

            if entry.accepted:
                logger.debug(
                    '{} {} was accepted, rerunning to look for next ep.',
                    entry['series_name'],
                    entry['series_id'],
                )
                self.rerun_entries.append(
                    self.search_entry(
                        series, entry['series_season'], entry['series_episode'] + 1, task
                    )
                )
                # Increase rerun limit by one if we have matches, this way
                # we keep searching as long as matches are found!
                # TODO: this should ideally be in discover so it would be more generic
                task.max_reruns += 1
                task.rerun(plugin='next_series_episodes', reason='Look for next episode')
            elif db_release:
                # There are know releases of this episode, but none were accepted
                return
            elif latest:
                if latest.is_season:
                    # A season pack was picked up in the task, no need to look for more episodes
                    return
                if (
                    not self.config.get('only_same_season')
                    and identified_by == 'ep'
                    and (
                        entry['series_season'] == latest.season
                        and entry['series_episode'] == latest.number + 1
                    )
                ):
                    # We searched for next predicted episode of this season unsuccessfully, try the next season
                    self.rerun_entries.append(
                        self.search_entry(series, latest.season + 1, 1, task)
                    )
                    logger.debug(
                        '{} {} not found, rerunning to look for next season',
                        entry['series_name'],
                        entry['series_id'],
                    )
                    task.rerun(plugin='next_series_episodes', reason='Look for next season')


@event('plugin.register')
def register_plugin():
    plugin.register(NextSeriesEpisodes, 'next_series_episodes', api_ver=2)
