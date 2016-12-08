from __future__ import unicode_literals, division, absolute_import

from functools import partial

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

from flexget.plugins.internal.api_tvdb import lookup_series, lookup_episode
from flexget.utils.database import with_session

log = logging.getLogger('thetvdb_lookup')


class PluginThetvdbLookup(object):
    """Retrieves TheTVDB information for entries. Uses series_name,
    series_season, series_episode from series plugin.

    Example:

    thetvdb_lookup: yes

    Primarily used for passing thetvdb information to other plugins.
    Among these is the IMDB url for the series.

    This information is provided (via entry):
    series info:
      tvdb_series_name
      tvdb_rating
      tvdb_status (Continuing or Ended)
      tvdb_runtime (show runtime in minutes)
      tvdb_first_air_date
      tvdb_air_time
      tvdb_content_rating
      tvdb_genres
      tvdb_network
      tvdb_overview
      tvdb_banner
      tvdb_posters
      tvdb_airs_day_of_week
      tvdb_actors
      tvdb_language (en, fr, etc.)
      imdb_url (if available)
      zap2it_id (if available)
    episode info: (if episode is found)
      tvdb_ep_name
      tvdb_ep_overview
      tvdb_ep_directors
      tvdb_ep_writers
      tvdb_ep_air_date
      tvdb_ep_rating
      tvdb_ep_guest_stars
      tvdb_ep_image
    """

    # Series info
    series_map = {
        'tvdb_series_name': 'name',
        'tvdb_rating': 'rating',
        'tvdb_status': 'status',
        'tvdb_runtime': 'runtime',
        'tvdb_first_air_date': 'first_aired',
        'tvdb_air_time': 'airs_time',
        'tvdb_content_rating': 'content_rating',
        'tvdb_genres': lambda series: [g for g in series.genres],
        'tvdb_network': 'network',
        'tvdb_overview': 'overview',
        'tvdb_banner': 'banner',
        'tvdb_language': 'language',
        'tvdb_airs_day_of_week': 'airs_dayofweek',
        'imdb_url': lambda series: series.imdb_id and 'http://www.imdb.com/title/%s' % series.imdb_id,
        'imdb_id': 'imdb_id',
        'zap2it_id': 'zap2it_id',
        'tvdb_id': 'id',
        'tvdb_url': lambda series: 'http://thetvdb.com/index.php?tab=series&id=%s' % str(series.id)
    }

    series_actor_map = {
        'tvdb_actors': 'actors',
    }
    series_poster_map = {
        'tvdb_posters': 'posters',
    }

    # Episode info
    episode_map = {
        'tvdb_ep_name': 'name',
        'tvdb_ep_air_date': 'first_aired',
        'tvdb_ep_rating': 'rating',
        'tvdb_ep_image': 'image',
        'tvdb_ep_overview': 'overview',
        'tvdb_ep_directors': 'director',
        'tvdb_absolute_number': 'absolute_number',
        'tvdb_season': 'season_number',
        'tvdb_episode': 'episode_number',
        'tvdb_ep_id': lambda ep: 'S%02dE%02d' % (ep.season_number, ep.episode_number)
    }

    schema = {'oneOf': [
        {'type': 'boolean'},
        {'type': 'object',
         'properties': {
             'language': {'type': 'string', 'default': 'en'}
         }}
    ]}

    @with_session
    def series_lookup(self, entry, language, field_map, session=None):
        try:
            series = lookup_series(
                entry.get('series_name', eval_lazy=False),
                tvdb_id=entry.get('tvdb_id', eval_lazy=False),
                language=entry.get('language', language),
                session=session
            )
            entry.update_using_map(field_map, series)
        except LookupError as e:
            log.debug('Error looking up tvdb series information for %s: %s', entry['title'], e.args[0])
        return entry

    def lazy_series_lookup(self, entry, language):
        return self.series_lookup(entry, language, self.series_map)

    def lazy_series_actor_lookup(self, entry, language):
        return self.series_lookup(entry, language, self.series_actor_map)

    def lazy_series_poster_lookup(self, entry, language):
        return self.series_lookup(entry, language, self.series_poster_map)

    def lazy_episode_lookup(self, entry, language):
        try:
            season_offset = entry.get('thetvdb_lookup_season_offset', 0)
            episode_offset = entry.get('thetvdb_lookup_episode_offset', 0)
            if not isinstance(season_offset, int):
                log.error('thetvdb_lookup_season_offset must be an integer')
                season_offset = 0
            if not isinstance(episode_offset, int):
                log.error('thetvdb_lookup_episode_offset must be an integer')
                episode_offset = 0
            if season_offset != 0 or episode_offset != 0:
                log.debug('Using offset for tvdb lookup: season: %s, episode: %s' % (season_offset, episode_offset))

            lookupargs = {'name': entry.get('series_name', eval_lazy=False),
                          'tvdb_id': entry.get('tvdb_id', eval_lazy=False),
                          'language': entry.get('language', language)}
            if entry['series_id_type'] == 'ep':
                lookupargs['season_number'] = entry['series_season'] + season_offset
                lookupargs['episode_number'] = entry['series_episode'] + episode_offset
            elif entry['series_id_type'] == 'sequence':
                lookupargs['absolute_number'] = entry['series_id'] + episode_offset
            elif entry['series_id_type'] == 'date':
                # TODO: Should thetvdb_lookup_episode_offset be used for date lookups as well?
                lookupargs['first_aired'] = entry['series_date']

            episode = lookup_episode(**lookupargs)
            entry.update_using_map(self.episode_map, episode)
        except LookupError as e:
            log.debug('Error looking up tvdb episode information for %s: %s', entry['title'], e.args[0])

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        if not config:
            return

        language = config['language'] if not isinstance(config, bool) else 'en'

        for entry in task.entries:
            # If there is information for a series lookup, register our series lazy fields
            if entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False):
                lazy_series_lookup = partial(self.lazy_series_lookup, language=language)
                lazy_series_actor_lookup = partial(self.lazy_series_actor_lookup, language=language)
                lazy_series_poster_lookup = partial(self.lazy_series_poster_lookup, language=language)

                entry.register_lazy_func(lazy_series_lookup, self.series_map)
                entry.register_lazy_func(lazy_series_actor_lookup, self.series_actor_map)
                entry.register_lazy_func(lazy_series_poster_lookup, self.series_poster_map)

                # If there is season and ep info as well, register episode lazy fields
                if entry.get('series_id_type') in ('ep', 'sequence', 'date'):
                    lazy_episode_lookup = partial(self.lazy_episode_lookup, language=language)
                    entry.register_lazy_func(lazy_episode_lookup, self.episode_map)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginThetvdbLookup, 'thetvdb_lookup', api_ver=2)
