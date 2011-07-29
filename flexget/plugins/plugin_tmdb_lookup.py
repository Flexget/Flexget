import logging
from flexget.plugin import get_plugin_by_name, priority, register_plugin, DependencyError
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

    fields = ['tmdb_name', 'tmdb_id', 'imdb_id', 'tmdb_year', 'tmdb_popularity', 'tmdb_rating', 'tmdb_genres']

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def lazy_loader(self, entry, field):
        """Does the lookup for this entry and populates the entry fields."""
        imdb_id = entry.get_no_lazy('imdb_id') or imdb.extract_id(entry.get('imdb_url', ''))
        try:
            movie = lookup(smart_match=entry['title'], tmdb_id=entry.get_no_lazy('tmdb_id'), imdb_id=imdb_id)
            entry['tmdb_name'] = movie.name
            entry['tmdb_id'] = movie.id
            entry['imdb_id'] = movie.imdb_id
            entry['tmdb_year'] = movie.year
            entry['tmdb_popularity'] = movie.popularity
            entry['tmdb_rating'] = movie.rating
            entry['tmdb_genres'] = [genre.name for genre in movie.genres]
            entry['tmdb_released'] = movie.released
            entry['tmdb_votes'] = movie.votes
            entry['tmdb_certification'] = movie.certification
            entry['tmdb_posters'] = [poster.url for poster in movie.posters]
            entry['tmdb_runtime'] = movie.runtime
            entry['tmdb_tagline'] = movie.tagline
            entry['tmdb_budget'] = movie.budget
            entry['tmdb_revenue'] = movie.revenue
            entry['tmdb_homepage'] = movie.homepage
            entry['tmdb_trailer'] = movie.trailer
            # TODO: other fields?
        except LookupError, e:
            log.debug('Tmdb lookup for %s failed: %s' % (entry['title'], e))
            # Set all of our fields to None if the lookup failed
            for f in self.fields:
                if entry.is_lazy(f):
                    entry[f] = None
        return entry[field]

    def register_lazy_fields(self, entry):
        entry.register_lazy_fields(self.fields, self.lazy_loader)

    def on_feed_metainfo(self, feed, config):
        if not config:
            return
        for entry in feed.entries:
            self.register_lazy_fields(entry)

register_plugin(PluginTmdbLookup, 'tmdb_lookup', api_ver=2)
