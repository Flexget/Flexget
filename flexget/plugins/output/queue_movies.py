from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.utils import qualities
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
        root = validator.factory()
        root.accept('boolean')
        opts = root.accept('dict')
        opts.accept('quality_requirements', key='quality')
        opts.accept('boolean', key='force')
        return root

    def on_task_output(self, task, config):
        if not config:
            return
        if not isinstance(config, dict):
            config = {}
        for entry in task.accepted:
            # Tell tmdb_lookup to add lazy lookup fields if not already present
            try:
                get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
            except DependencyError:
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

            # since entries usually have unknown quality we need to ignore that ..
            if entry.get('quality'):
                quality = qualities.Requirements(entry['quality'].name)
            else:
                quality = qualities.Requirements(config.get('quality', 'any'))

            kwargs['quality'] = quality
            force = entry.get('force', config.get('force'))
            if force is not None:
                kwargs['force'] = force
            # Provide movie title if it is already available, to avoid movie_queue doing a lookup
            kwargs['title'] = (entry.get('imdb_name', eval_lazy=False) or
                               entry.get('tmdb_name', eval_lazy=False) or
                               entry.get('movie_name', eval_lazy=False))
            log.debug('queueing kwargs: %s' % kwargs)
            try:
                queue_add(**kwargs)
            except QueueError as e:
                # Ignore already in queue errors
                if e.errno != 1:
                    entry.fail('Error adding movie to queue: %s' % e.message)


register_plugin(QueueMovies, 'queue_movies', api_ver=2)
