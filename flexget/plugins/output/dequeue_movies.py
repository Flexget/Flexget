from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities

try:
    from flexget.plugins.filter.movie_queue import queue_del, QueueError
except ImportError:
    raise plugin.DependencyError(issued_by='dequeue_movies', missing='movie_queue')

log = logging.getLogger('dequeue_movies')

class DequeueMovies(object):
    """Removes all accepted entries from your movie queue."""

    schema = {'type': 'boolean'}

    def on_task_output(self, task, config):
        if not config:
            return
        if not isinstance(config, dict):
            config = {}
        for entry in task.accepted:
            # Tell tmdb_lookup to add lazy lookup fields if not already present
            try:
                plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
            except plugin.DependencyError:
                log.debug('tmdb_lookup is not available, queue will not work if movie ids are not populated')
            # Find one or both movie id's for this entry. See if an id is already populated before incurring lazy lookup
            kwargs = {}
            for lazy in [False, True]:
                if entry.get('imdb_id', eval_lazy=lazy):
                    kwargs['imdb_id'] = entry['imdb_id']
                if entry.get('tmdb_id', eval_lazy=lazy):
                    kwargs['tmdb_id'] = entry['tmdb_id']
                if kwargs:
                    break
            if not kwargs:
                log.warning('Could not determine a movie id for %s, it will not be added to queue.' % entry['title'])
                continue

            # Provide movie title if it is already available, to avoid movie_queue doing a lookup
            kwargs['title'] = (entry.get('imdb_name', eval_lazy=False) or
                               entry.get('tmdb_name', eval_lazy=False) or
                               entry.get('movie_name', eval_lazy=False))
            log.debug('dequeueing kwargs: %s' % kwargs)
            try:
                queue_del(**kwargs)
            except QueueError as e:
                # Ignore already in queue errors
                if e.errno != 1:
                    entry.fail('Error removing movie from queue: %s' % e.message)


@event('plugin.register')
def register_plugin():
    plugin.register(DequeueMovies, 'dequeue_movies', api_ver=2)
