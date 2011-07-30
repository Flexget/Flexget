import logging
from flexget.plugin import register_plugin, DependencyError
from flexget.utils import imdb

try:
    # TODO: Fix this after api_tmdb has module level functions
    from flexget.plugins.api_tmdb import ApiTmdb
    lookup = ApiTmdb.lookup
except ImportError:
    raise DependencyError(issued_by='tmdb_lookup', missing='api_tmdb')

log = logging.getLogger('tmdb_lookup')


class PluginTmdbLookup(object):
    """Retrieves tmdb information for entries.

    Example:
        tmdb_lookup: yes
    """

    field_map = {
        'tmdb_name': 'name',
        'tmdb_id': 'id',
        'imdb_id': 'imdb_id',
        'tmdb_year': 'year',
        'tmdb_popularity': 'popularity',
        'tmdb_rating': 'rating',
        'tmdb_genres': lambda movie: [genre.name for genre in movie.genres],
        'tmdb_released': 'released',
        'tmdb_votes': 'votes',
        'tmdb_certification': 'certification',
        'tmdb_posters': lambda movie: [poster.url for poster in movie.posters],
        'tmdb_runtime': 'runtime',
        'tmdb_tagline': 'tagline',
        'tmdb_budget': 'budget',
        'tmdb_revenue': 'revenue',
        'tmdb_homepage': 'homepage',
        'tmdb_trailer': 'trailer'}

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def lazy_loader(self, entry, field):
        """Does the lookup for this entry and populates the entry fields."""
        imdb_id = entry.get_no_lazy('imdb_id') or imdb.extract_id(entry.get_no_lazy('imdb_url'))
        try:
            movie = lookup(smart_match=entry['title'], tmdb_id=entry.get_no_lazy('tmdb_id'), imdb_id=imdb_id)
            entry.update_using_map(self.field_map, movie)
        except LookupError, e:
            log.debug('Tmdb lookup for %s failed: %s' % (entry['title'], e))
            # Set all of our fields to None if the lookup failed
            for f in self.field_map:
                if entry.is_lazy(f):
                    entry[f] = None
        return entry[field]

    def on_feed_metainfo(self, feed, config):
        if not config:
            return
        for entry in feed.entries:
            entry.register_lazy_fields(self.field_map, self.lazy_loader)

register_plugin(PluginTmdbLookup, 'tmdb_lookup', api_ver=2)
