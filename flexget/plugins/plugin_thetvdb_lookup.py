import logging
from flexget.plugin import get_plugin_by_name, register_plugin, DependencyError, priority

try:
    from flexget.plugins.api_tvdb import lookup_episode, get_mirror
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

    # Run after series and metainfo series
    @priority(115)
    def on_feed_metainfo(self, feed, config):
        if not config:
            return
        field_map = {
            # Series info
            'series_name_tvdb': 'series.seriesname',
            'series_rating': 'series.rating',
            'series_status': 'series.status',
            'series_runtime': 'series.runtime',
            'series_first_air_date': 'series.firstaired',
            'series_air_time': 'series.airs_time',
            'series_content_rating': 'series.contentrating',
            'series_genres': 'series.genre',
            'series_network': 'series.network',
            'series_banner_url': lambda ep: ep.series.banner and get_mirror('banner') + ep.series.banner,
            'series_fanart_url': lambda ep: ep.series.fanart and get_mirror('banner') + ep.series.fanart,
            'series_poster_url': lambda ep: ep.series.poster and get_mirror('banner') + ep.series.poster,
            'series_airs_day_of_week': 'series.airs_dayofweek',
            'series_language': 'series.language',
            'imdb_url': lambda ep: ep.series.imdb_id and 'http://www.imdb.com/title/%s' % ep.series.imdb_id,
            'imdb_id': 'series.imdb_id',
            'zap2it_id': 'series.zap2it_id',
            'thetvdb_id': 'series.id',
            # Episode info
            'ep_name': 'episodename',
            'ep_air_date': 'firstaired',
            'ep_rating': 'rating',
            'ep_image_url': lambda ep: ep.filename and get_mirror('banner') + ep.filename,
            'ep_overview': 'overview',
            'ep_writers': 'writer',
            'ep_directors': 'director',
            'ep_guest_stars': 'guest_stars'}

        def populate_fields(entry, episode):
            """Populates entry fields from episode using the field_map"""
            for field, value in field_map.iteritems():
                if isinstance(value, basestring):
                    # If a string is passed, it is an attribute of episode (supporting nested attributes)
                    entry[field] = reduce(getattr, value.split('.'), episode)
                else:
                    # Otherwise a function that takes episode as an argument
                    entry[field] = value(episode)

        def lazy_loader(entry, field):
            """Does the lookup for this entry and populates the entry fields."""
            try:
                episode = lookup_episode(entry.get_no_lazy('series_name'), entry['series_season'],
                                         entry['series_episode'], tvdb_id=entry.get_no_lazy('thetvdb_id'))
            except LookupError, e:
                log.debug('Error looking up tvdb information for %s: %s' % (entry['title'], e.message))
                # Set all of our fields to None if the lookup failed
                for f in field_map:
                    if entry.is_lazy(f):
                        entry[f] = None
            else:
                populate_fields(entry, episode)
            return entry[field]

        for entry in feed.entries:
            if not (entry.get('series_name') or entry.get('thetvdb_id')) or not \
                    entry.get('series_season') or not entry.get('series_episode'):
                # If entry does not have series info we cannot do lookup
                continue
            entry.register_lazy_fields(field_map, lazy_loader)


register_plugin(PluginThetvdbLookup, 'thetvdb_lookup', api_ver=2)
