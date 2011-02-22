from flexget.plugin import get_plugin_by_name, priority, register_plugin
from flexget.plugins.api_tvdb import lookup_episode


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

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_process_start(self, feed):
        """Register the usable set plugin keywords"""
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_key('thetvdb_id', 'integer')

    @priority(120)
    def on_feed_filter(self, feed):
        for entry in feed.entries:
            if not (entry.get('series_name') or entry.get('thetvdb_id')) or not \
                    entry.get('series_season') or not entry.get('series_episode'):
                # If entry does not have series info we cannot do lookup
                continue
            episode = lookup_episode(entry.get('series_name'), entry['series_season'], entry['series_episode'],
                                     tvdb_id=entry.get('thetvdb_id'))
            if episode:
                # Series info
                entry['series_name_tvdb'] = episode.series.seriesname
                entry['series_rating'] = episode.series.rating
                entry['series_status'] = episode.series.status
                entry['series_runtime'] = episode.series.runtime
                entry['series_first_air_date'] = episode.series.firstaired
                entry['series_air_time'] = episode.series.airs_time
                entry['series_content_rating'] = episode.series.contentrating
                entry['series_genres'] = episode.series.genre
                entry['series_network'] = episode.series.network
                entry['series_banner_url'] = "http://www.thetvdb.com/banners/%s" % episode.series.banner
                entry['series_fanart_url'] = "http://www.thetvdb.com/banners/%s" % episode.series.fanart
                entry['series_poster_url'] = "http://www.thetvdb.com/banners/%s" % episode.series.poster
                entry['series_airs_day_of_week'] = episode.series.airs_dayofweek
                entry['series_language'] = episode.series.language
                entry['imdb_url'] = "http://www.imdb.com/title/%s" % episode.series.imdb_id
                entry['imdb_id'] = episode.series.imdb_id
                entry['zap2it_id'] = episode.series.zap2it_id
                entry['thetvdb_id'] = episode.series.id
                # Episode info
                entry['ep_name'] = episode.episodename
                entry['ep_air_date'] = episode.firstaired
                entry['ep_rating'] = episode.rating
                entry['ep_image_url'] = "http://www.thetvdb.com/banners/%s" % episode.filename
                entry['ep_overview'] = episode.overview
                entry['ep_writers'] = episode.writer
                entry['ep_directors'] = episode.director
                entry['ep_guest_stars'] = episode.guest_stars


register_plugin(PluginThetvdbLookup, 'thetvdb_lookup')
