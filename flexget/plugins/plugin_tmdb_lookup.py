import logging
from flexget.plugin import get_plugin_by_name, priority, register_plugin
from flexget.utils import imdb

log = logging.getLogger('tmdb_lookup')


class PluginTmdbLookup(object):
    """
        Retrieves tmdb information for entries.

        Example:

        tmdb_lookup: yes
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(100)
    def on_feed_filter(self, feed, config):
        if not config:
            return
        lookup = get_plugin_by_name('api_tmdb').instance.lookup
        fields = ['tmdb_name', 'tmdb_id', 'imdb_id', 'tmdb_year', 'tmdb_popularity', 'tmdb_rating', 'tmdb_genres']

        def lazy_loader(entry, field):
            """Does the lookup for this entry and populates the entry fields."""
            imdb_id = entry.get_no_lazy('imdb_id') or imdb.extract_id(entry.get('imdb_url', ''))
            movie = lookup(smart_match=entry['title'], tmdb_id=entry.get_no_lazy('tmdb_id'), imdb_id=imdb_id)
            if movie:
                entry['tmdb_name'] = movie.name
                entry['tmdb_id'] = movie.id
                entry['imdb_id'] = movie.imdb_id
                entry['tmdb_year'] = movie.year
                entry['tmdb_popularity'] = movie.popularity
                entry['tmdb_rating'] = movie.rating
                entry['tmdb_genres'] = [genre.name for genre in movie.genres]
                # TODO: other fields?
            else:
                log.debug('Tmdb lookup for %s failed.' % entry['title'])
                # Set all of our fields to None if the lookup failed
                for f in fields:
                    if entry.is_lazy(f):
                        entry[f] = None
            return entry[field]

        for entry in feed.entries:
            entry.register_lazy_fields(fields, lazy_loader)

register_plugin(PluginTmdbLookup, 'tmdb_lookup', api_ver=2)
