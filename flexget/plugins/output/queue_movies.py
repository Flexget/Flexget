import logging
from flexget.plugin import register_plugin, get_plugin_by_name, DependencyError

try:
    from flexget.plugins.filter.movie_queue import queue_add, QueueError
except ImportError:
    raise DependencyError(issued_by='queue_movies', missing='movie_queue')

log = logging.getLogger('queue_movies')


class QueueMovies(object):
    """Adds all accepted entries to your movie queue."""

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_output(self, feed, config):
        if not config:
            return
        for entry in feed.accepted:
            # Tell tmdb_lookup to add lazy lookup fields if not already present
            try:
                get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
            except DependencyError:
                log.debug('tmdb_lookup is not available, queue will not work if movie ids are not populated')
            # Find one or both movie id's for this entry. See if an id is already populated before incurring lazy lookup
            kwargs = {}
            for lazy in [False, True]:
                if entry.get('imdb_id', lazy=lazy):
                    kwargs['imdb_id'] = entry['imdb_id']
                if entry.get('tmdb_id', lazy=lazy):
                    kwargs['tmdb_id'] = entry['tmdb_id']
                if kwargs:
                    break
            if not kwargs:
                log.warning('Could not determine a movie id for %s, it will not be added to queue.' % entry['title'])
                continue
            if entry.get('quality'):
                kwargs['quality'] = entry.get('quality')
            try:
                queue_add(**kwargs)
            except QueueError, e:
                feed.fail(entry, 'Error addd movie to queue: %s' % e.message)


register_plugin(QueueMovies, 'queue_movies', api_ver=2)
