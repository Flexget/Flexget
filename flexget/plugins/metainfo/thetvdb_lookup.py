import logging
from flexget.plugin import get_plugin_by_name, register_plugin, DependencyError, priority

try:
    from flexget.plugins.api_tvdb import lookup_series, lookup_episode, get_mirror
except ImportError:
    raise DependencyError(issued_by='thetvdb_lookup', missing='api_tvdb',
                          message='thetvdb_lookup requires the `api_tvdb` plugin')

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
      series_name_thetvdb
      series_rating
      series_status (Continuing or Ended)
      series_runtime (show runtime in minutes)
      series_first_air_date
      series_air_time
      series_content_rating
      series_genres
      series_network
      series_banner_url
      series_fanart_url
      series_poster_url
      series_airs_day_of_week
      series_actors
      series_language (en, fr, etc.)
      imdb_url (if available)
      zap2it_id (if available)
    episode info: (if episode is found)
      ep_name
      ep_overview
      ep_directors
      ep_writers
      ep_air_date
      ep_rating
      ep_guest_stars
      ep_image_url
    """

    # Series info
    series_map = {
        'series_name_tvdb': 'seriesname',
        'series_rating': 'rating',
        'series_status': 'status',
        'series_runtime': 'runtime',
        'series_first_air_date': 'firstaired',
        'series_air_time': 'airs_time',
        'series_content_rating': 'contentrating',
        'series_genres': 'genre',
        'series_network': 'network',
        'series_banner_url': lambda series: series.banner and get_mirror('banner') + series.banner,
        'series_fanart_url': lambda series: series.fanart and get_mirror('banner') + series.fanart,
        'series_poster_url': lambda series: series.poster and get_mirror('banner') + series.poster,
        'series_airs_day_of_week': 'airs_dayofweek',
        'series_language': 'language',
        'imdb_url': lambda series: series.imdb_id and 'http://www.imdb.com/title/%s' % series.imdb_id,
        'imdb_id': 'imdb_id',
        'zap2it_id': 'zap2it_id',
        'thetvdb_id': 'id'}
    # Episode info
    episode_map = {
        'ep_name': 'episodename',
        'ep_air_date': 'firstaired',
        'ep_rating': 'rating',
        'ep_image_url': lambda ep: ep.filename and get_mirror('banner') + ep.filename,
        'ep_overview': 'overview',
        'ep_writers': 'writer',
        'ep_directors': 'director',
        'ep_guest_stars': 'gueststars'}

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_start(self, feed, config):
        """Register the usable set plugin keywords"""
        try:
            set_plugin = get_plugin_by_name('set')
            set_plugin.instance.register_key('thetvdb_id', 'integer')
        except DependencyError:
            pass

    def lazy_series_lookup(self, entry, field):
        """Does the lookup for this entry and populates the entry fields."""
        try:
            series = lookup_series(entry.get('series_name', lazy=False), tvdb_id=entry.get('thetvdb_id', lazy=False))
            entry.update_using_map(self.series_map, series)
        except LookupError, e:
            log.debug('Error looking up tvdb series information for %s: %s' % (entry['title'], e.message))
            entry.unregister_lazy_fields(self.series_map, self.lazy_series_lookup)
            # Also clear episode fields, since episode lookup cannot succeed without series lookup
            entry.unregister_lazy_fields(self.episode_map, self.lazy_episode_lookup)

        return entry[field]

    def lazy_episode_lookup(self, entry, field):
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

            episode = lookup_episode(entry.get('series_name', lazy=False),
                                     entry['series_season'] + season_offset,
                                     entry['series_episode'] + episode_offset,
                                     tvdb_id=entry.get('thetvdb_id', lazy=False))
            entry.update_using_map(self.episode_map, episode)
        except LookupError, e:
            log.debug('Error looking up tvdb episode information for %s: %s' % (entry['title'], e.message))
            entry.unregister_lazy_fields(self.episode_map, self.lazy_episode_lookup)

        return entry[field]

    # Run after series and metainfo series
    @priority(110)
    def on_feed_metainfo(self, feed, config):
        if not config:
            return

        for entry in feed.entries:
            # If there is information for a series lookup, register our series lazy fields
            if entry.get('series_name') or entry.get('thetvdb_id', lazy=False):
                entry.register_lazy_fields(self.series_map, self.lazy_series_lookup)

                # If there is season and ep info as well, register episode lazy fields
                if entry.get('series_season') and entry.get('series_episode'):
                    entry.register_lazy_fields(self.episode_map, self.lazy_episode_lookup)


register_plugin(PluginThetvdbLookup, 'thetvdb_lookup', api_ver=2)
