from __future__ import unicode_literals, division, absolute_import

import logging
import re

from flexget import plugin
from flexget.event import event

try:
    from flexget.plugins.api_tvmaze import APITVMaze

    lookup = APITVMaze.episode_lookup
except ImportError:
    raise plugin.DependencyError(issued_by='est_series_tvmaze', missing='api_tvmaze',
                                 message='est_series_tvmaze requires the `api_tvmaze` plugin')

log = logging.getLogger('est_series_tvmaze')


class EstimatesSeriesTVMaze(object):
    @plugin.priority(2)
    def estimate(self, entry):
        if not all(field in entry for field in ['series_name', 'series_season', 'series_episode']):
            return
        series_name = entry['series_name']
        season = entry['series_season']
        episode_number = entry['series_episode']
        year_match = re.search('\(([\d]{4})\)', series_name)  # Gets year from title if present
        if year_match:
            year_match = year_match.group(1)

        kwargs = {}
        kwargs['maze_id'] = entry.get('tvmaze_id')
        kwargs['tvdb_id'] = entry.get('tvdb_id') or entry.get('trakt_series_tvdb_id')
        kwargs['tvrage_id'] = entry.get('tvrage_id') or entry.get('trakt_series_tvrage_id')
        kwargs['show_name'] = re.sub('\(([\d]{4})\)', '', series_name).rstrip()  # Remove year from name if present
        kwargs['show_year'] = entry.get('trakt_series_year') or entry.get('year') or entry.get(
            'imdb_year') or year_match
        kwargs['show_network'] = entry.get('network') or entry.get('trakt_series_network')
        kwargs['show_country'] = entry.get('country') or entry.get('trakt_series_country')
        kwargs['show_language'] = entry.get('language')
        kwargs['series_season'] = season
        kwargs['series_episode'] = episode_number
        kwargs['series_name'] = series_name

        log.debug(
            'Searching TVMaze for airdate of {0} season {1} episode {2}'.format(series_name, season, episode_number))
        for k, v in kwargs.items():
            if v:
                log.debug('{0}: {1}'.format(k, v))
        try:
            episode = lookup(**kwargs)
        except LookupError as e:
            log.debug(e)
            return
        if episode and episode.airdate:
            log.debug('received airdate: {0}'.format(episode.airdate))
            return episode.airdate
        return


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesSeriesTVMaze, 'est_series_tvmaze', groups=['estimate_release'], api_ver=2)
