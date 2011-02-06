from flexget.plugin import get_plugin_by_name, priority, register_plugin
from flexget.utils import imdb


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
    def on_feed_filter(self, feed):
        lookup = get_plugin_by_name('api_tmdb').instance.lookup
        for entry in feed.entries:
            imdb_id = entry.get('imdb_id') or imdb.extract_id(entry.get('imdb_url', ''))
            movie = lookup(title=entry['title'], tmdb_id=entry.get('tmdb_id'), imdb_id=imdb_id)
            if movie:
                entry['tmdb_name'] = movie.name
                entry['tmdb_id'] = movie.id
                entry['imdb_id'] = movie.imdb_id
                entry['tmdb_year'] = movie.released.year
                entry['tmdb_popularity'] = movie.popularity
                entry['tmdb_rating'] = movie.rating
                entry['tmdb_genres'] = [genre.name for genre in movie.genres]
                # TODO: other fields?

register_plugin(PluginTmdbLookup, 'tmdb_lookup')
