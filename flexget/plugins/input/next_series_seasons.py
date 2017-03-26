from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.manager import Session
from flexget.plugins.filter.series import SeriesTask, Series, get_latest_release, get_latest_season_pack_release

plugin_name = 'next_series_seasons'
log = logging.getLogger(plugin_name)


class NextSeriesSeasons(object):
    """
    Emit next season number from all series configured in this task.

    Supports only 'ep' mode series.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'from_start': {'type': 'boolean', 'default': False},
                    'backfill': {'type': 'boolean', 'default': False}
                },
                'additionalProperties': False
            }
        ]
    }

    def __init__(self):
        self.rerun_entries = []

    def season_identifiers(self, season):
        return ['S%02d' % season]

    def search_entry(self, series, season, task, rerun=True):
        # Extract the alternate names for the series
        alts = [alt.alt_name for alt in series.alternate_names]
        # Also consider series name without parenthetical (year, country) an alternate name
        paren_match = re.match(r'(.+?)( \(.+\))?$', series.name)
        if paren_match.group(2):
            alts.append(paren_match.group(1))
        search_strings = ['%s %s' % (series.name, id) for id in self.season_identifiers(season)]
        series_id = 'S%02d' % season
        for alt in alts:
            search_strings.extend(['%s %s' % (alt, id) for id in self.season_identifiers(season)])
        entry = Entry(title=search_strings[0], url='',
                      search_strings=search_strings,
                      series_name=series.name,
                      series_alternate_names=alts,  # Not sure if this field is useful down the road.
                      series_season=season,
                      season_pack=True,
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

                if series.identified_by not in ['ep']:
                    log.trace('unsupported identified_by scheme')
                    reason = series.identified_by or 'auto'
                    impossible.setdefault(reason, []).append(series.name)
                    continue

                low_season = 0

                check_downloaded = not config.get('backfill')
                latest_season = get_latest_release(series, downloaded=check_downloaded)
                if latest_season:
                    latest_season = latest_season.season
                else:
                    latest_season = low_season + 1

                for season in range(latest_season, low_season, -1):
                    if season in series.completed_seasons:
                        log.debug('season %s is marked as completed, skipping', season)
                        continue
                    log.trace('Adding episodes for series %s season %d', series.name, season)
                    latest = get_latest_release(series, season=season, downloaded=check_downloaded)
                    if series.begin and (not latest or latest < series.begin):
                        # In case series.begin season is already completed, look in next available season
                        lookup_season = series.begin.season
                        while lookup_season in series.completed_seasons:
                            lookup_season += 1
                        entries.append(self.search_entry(series, lookup_season, task))
                    elif latest:
                        entries.append(self.search_entry(series, latest.season, task))
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
                        break
                    # Don't look for seasons older than begin ep
                    if series.begin and series.begin.season >= season:
                        break

        for reason, series in impossible.items():
            log.verbose('Series `%s` with identified_by value `%s` are not supported. ',
                        ', '.join(sorted(series)), reason)

        return entries

    def on_search_complete(self, entry, task=None, identified_by=None, **kwargs):
        """Decides whether we should look for next season based on whether we found/accepted any seasons."""
        with Session() as session:
            series = session.query(Series).filter(Series.name == entry['series_name']).first()
            latest = get_latest_season_pack_release(series)

            if entry.accepted:
                log.debug('%s %s was accepted, rerunning to look for next season.' % (
                    entry['series_name'], entry['series_id']))
                self.rerun_entries.append(self.search_entry(series, entry['series_season'] + 1, task))
                # Increase rerun limit by one if we have matches, this way
                # we keep searching as long as matches are found!
                # TODO: this should ideally be in discover so it would be more generic
                task.max_reruns += 1
                task.rerun(plugin=plugin_name, reason='Look for next season')
            elif latest and not latest.completed:
                # There are known releases of this season, but none were accepted
                return


@event('plugin.register')
def register_plugin():
    plugin.register(NextSeriesSeasons, plugin_name, api_ver=2)
