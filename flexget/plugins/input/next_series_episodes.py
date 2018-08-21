from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from sqlalchemy import desc

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.filter.series import SeriesTask, Series, Episode, EpisodeRelease, get_latest_release

log = logging.getLogger('next_series_episodes')


class NextSeriesEpisodes(object):
    """
    Emit next episode number from all series configured in this task.

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
                    'only_same_season': {'type': 'boolean', 'default': False}
                },
                'additionalProperties': False
            }
        ]
    }

    def __init__(self):
        self.rerun_entries = []

    def ep_identifiers(self, season, episode):
        return ['S%02dE%02d' % (season, episode),
                '%dx%02d' % (season, episode)]

    def sequence_identifiers(self, episode):
        # Use a set to remove doubles, which will happen depending on number of digits in episode
        return {'%d' % episode, '%02d' % episode, '%03d' % episode}

    def search_entry(self, series, season, episode, task, rerun=True):
        # Extract the alternate names for the series
        alts = [alt.alt_name for alt in series.alternate_names]
        # Also consider series name without parenthetical (year, country) an alternate name
        paren_match = re.match(r'(.+?)( \(.+\))?$', series.name)
        if paren_match.group(2):
            alts.append(paren_match.group(1))
        if series.identified_by == 'ep':
            search_strings = ['%s %s' % (series.name, id) for id in self.ep_identifiers(season, episode)]
            series_id = 'S%02dE%02d' % (season, episode)
            for alt in alts:
                search_strings.extend(['%s %s' % (alt, id) for id in self.ep_identifiers(season, episode)])
        else:
            search_strings = ['%s %s' % (series.name, id) for id in self.sequence_identifiers(episode)]
            series_id = episode
            for alt in alts:
                search_strings.extend(['%s %s' % (alt, id) for id in self.sequence_identifiers(episode)])
        entry = Entry(title=search_strings[0], url='',
                      search_strings=search_strings,
                      series_name=series.name,
                      series_alternate_names=alts,  # Not sure if this field is useful down the road.
                      series_season=season,
                      series_episode=episode,
                      season_pack_lookup=False,
                      series_id=series_id,
                      series_id_type=series.identified_by)
        if rerun:
            entry.on_complete(self.on_search_complete, task=task, identified_by=series.identified_by)
        return entry

    def on_task_input(self, task, config):
        if not config:
            return
        if isinstance(config, bool):
            config = {}
        self.config = config
        if task.is_rerun:
            # Just return calculated next eps on reruns
            entries = self.rerun_entries
            self.rerun_entries = []
            return entries
        else:
            self.rerun_entries = []

        entries = []
        impossible = {}
        with Session() as session:
            for seriestask in session.query(SeriesTask).filter(SeriesTask.name == task.name).all():
                series = seriestask.series
                log.trace('evaluating %s', series.name)
                if not series:
                    # TODO: How can this happen?
                    log.debug('Found SeriesTask item without series specified. Cleaning up.')
                    session.delete(seriestask)
                    continue

                if series.identified_by not in ['ep', 'sequence']:
                    log.trace('unsupported identified_by scheme')
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
                latest_season = get_latest_release(series, downloaded=check_downloaded)
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
                        log.debug('season %s is marked as completed, skipping', season)
                        continue
                    log.trace('Evaluating episodes for series %s, season %d', series.name, season)
                    latest = get_latest_release(series, season=season, downloaded=check_downloaded)
                    if series.begin and season == series.begin.season and (not latest or latest < series.begin):
                        # In case series.begin season is already completed, look in next available season
                        lookup_season = series.begin.season
                        ep_number = series.begin.number
                        while lookup_season in series.completed_seasons:
                            lookup_season += 1
                            # If season number was bumped, start looking for ep 1
                            ep_number = 1
                        entries.append(self.search_entry(series, lookup_season, ep_number, task))
                    elif latest and not config.get('backfill'):
                        entries.append(self.search_entry(series, latest.season, latest.number + 1, task))
                    elif latest:
                        start_at_ep = 1
                        episodes_this_season = (session.query(Episode).
                                                filter(Episode.series_id == series.id).
                                                filter(Episode.season == season))
                        if series.identified_by == 'sequence':
                            # Don't look for missing too far back with sequence shows
                            start_at_ep = max(latest.number - 10, 1)
                            episodes_this_season = episodes_this_season.filter(Episode.number >= start_at_ep)
                        latest_ep_this_season = episodes_this_season.order_by(desc(Episode.number)).first()
                        if latest_ep_this_season:
                            downloaded_this_season = (episodes_this_season.join(Episode.releases).
                                                      filter(EpisodeRelease.downloaded == True).all())
                            # Calculate the episodes we still need to get from this season
                            if series.begin and series.begin.season == season:
                                start_at_ep = max(start_at_ep, series.begin.number)
                            eps_to_get = list(range(start_at_ep, latest_ep_this_season.number + 1))
                            for ep in downloaded_this_season:
                                try:
                                    eps_to_get.remove(ep.number)
                                except ValueError:
                                    pass
                            entries.extend(self.search_entry(series, season, x, task, rerun=False) for x in eps_to_get)
                            # If we have already downloaded the latest known episode, try the next episode
                            if latest_ep_this_season.releases:
                                entries.append(
                                    self.search_entry(series, season, latest_ep_this_season.number + 1, task))
                        else:
                            # No episode means that latest is a season pack, emit episode 1
                            entries.append(self.search_entry(series, season, 1, task))
                    # First iteration of a new season with no show begin and show has downloads
                    elif new_season and season == new_season:
                        entries.append(self.search_entry(series, season, 1, task))
                    else:
                        if config.get('from_start') or config.get('backfill'):
                            entries.append(self.search_entry(series, season, 1, task))
                        else:
                            log.verbose('Series `%s` has no history. Set begin option, '
                                        'or use CLI `series begin` '
                                        'subcommand to set first episode to emit', series.name)
                            break
                    # Skip older seasons if we are not in backfill mode
                    if not config.get('backfill'):
                        log.debug('backfill is not enabled; skipping older seasons')
                        break

        for reason, series in impossible.items():
            log.verbose('Series `%s` with identified_by value `%s` are not supported. ',
                        ', '.join(sorted(series)), reason)

        return entries

    def on_search_complete(self, entry, task=None, identified_by=None, **kwargs):
        """Decides whether we should look for next ep/season based on whether we found/accepted any episodes."""
        with Session() as session:
            series = session.query(Series).filter(Series.name == entry['series_name']).first()
            latest = get_latest_release(series)
            db_release = (session.query(EpisodeRelease).join(EpisodeRelease.episode).join(Episode.series).
                          filter(Series.name == entry['series_name']).
                          filter(Episode.season == entry['series_season']).
                          filter(Episode.number == entry['series_episode']).first())

            if entry.accepted:
                log.debug('%s %s was accepted, rerunning to look for next ep.' %
                          (entry['series_name'], entry['series_id']))
                self.rerun_entries.append(self.search_entry(series,
                                                            entry['series_season'],
                                                            entry['series_episode'] + 1,
                                                            task))
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
                elif not self.config.get('only_same_season') and identified_by == 'ep' and (
                            entry['series_season'] == latest.season and entry['series_episode'] == latest.number + 1):
                    # We searched for next predicted episode of this season unsuccessfully, try the next season
                    self.rerun_entries.append(self.search_entry(series, latest.season + 1, 1, task))
                    log.debug('%s %s not found, rerunning to look for next season' %
                              (entry['series_name'], entry['series_id']))
                    task.rerun(plugin='next_series_episodes', reason='Look for next season')


@event('plugin.register')
def register_plugin():
    plugin.register(NextSeriesEpisodes, 'next_series_episodes', api_ver=2)
