from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import split_title_year

log = logging.getLogger('est_series_tvmaze')


class EstimatesSeriesTVMaze(object):
    @plugin.priority(2)
    def estimate(self, entry):
        if not all(field in entry for field in ['series_name', 'series_season']):
            return
        series_name = entry['series_name']
        season = entry['series_season']
        episode_number = entry.get('series_episode')
        title, year_match = split_title_year(series_name)

        # This value should be added to input plugins to trigger a season lookuo
        season_pack = entry.get('season_pack_lookup')

        kwargs = {
            'tvmaze_id': entry.get('tvmaze_id'),
            'tvdb_id': entry.get('tvdb_id') or entry.get('trakt_series_tvdb_id'),
            'tvrage_id': entry.get('tvrage_id') or entry.get('trakt_series_tvrage_id'),
            'imdb_id': entry.get('imdb_id'),
            'show_name': title,
            'show_year': entry.get('trakt_series_year')
            or entry.get('year')
            or entry.get('imdb_year')
            or year_match,
            'show_network': entry.get('network') or entry.get('trakt_series_network'),
            'show_country': entry.get('country') or entry.get('trakt_series_country'),
            'show_language': entry.get('language'),
            'series_season': season,
            'series_episode': episode_number,
            'series_name': series_name,
        }

        api_tvmaze = plugin.get('api_tvmaze', self)
        if season_pack:
            lookup = api_tvmaze.season_lookup
            log.debug('Searching api_tvmaze for season')
        else:
            log.debug('Searching api_tvmaze for episode')
            lookup = api_tvmaze.episode_lookup

        for k, v in list(kwargs.items()):
            if v:
                log.debug('%s: %s', k, v)

        try:
            entity = lookup(**kwargs)
        except LookupError as e:
            log.debug(str(e))
            return
        if entity and entity.airdate:
            log.debug('received air-date: %s', entity.airdate)
            return entity.airdate
        return


@event('plugin.register')
def register_plugin():
    plugin.register(
        EstimatesSeriesTVMaze, 'est_series_tvmaze', interfaces=['estimate_release'], api_ver=2
    )
