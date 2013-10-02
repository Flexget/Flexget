from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.filter.seen import FilterSeen

log = logging.getLogger('seenmovies')


class FilterSeenMovies(FilterSeen):
    """
        Prevents movies being downloaded twice.
        Works only on entries which have imdb url available.

        How duplicate movie detection works:
        1) Remember all imdb urls from downloaded entries.
        2) If stored imdb url appears again, entry is rejected.
    """

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['imdb_id', 'tmdb_id']
        self.keyword = 'seen_movies'

    def validator(self):
        from flexget import validator
        root = validator.factory('choice', message="must be one of the following: strict, loose")
        root.accept_choices(['strict', 'loose'])
        return root

    # We run last (-255) to make sure we don't reject duplicates before all the other plugins get a chance to reject.
    @plugin.priority(-255)
    def on_task_filter(self, task, config):
        # strict method
        if config == 'strict':
            for entry in task.entries:
                if 'imdb_id' not in entry and 'tmdb_id' not in entry:
                    log.info('Rejecting %s because of missing movie (imdb or tmdb) id' % entry['title'])
                    entry.reject('missing movie (imdb or tmdb) id, strict')
        # call super
        super(FilterSeenMovies, self).on_task_filter(task, True)
        # check that two copies of a movie have not been accepted this run
        imdb_ids = set()
        tmdb_ids = set()
        for entry in task.accepted:
            if 'imdb_id' in entry:
                if entry['imdb_id'] in imdb_ids:
                    entry.reject('already accepted once in task')
                    continue
                else:
                    imdb_ids.add(entry['imdb_id'])
            if 'tmdb_id' in entry:
                if entry['tmdb_id'] in tmdb_ids:
                    entry.reject('already accepted once in task')
                    continue
                else:
                    tmdb_ids.add(entry['tmdb_id'])

@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeenMovies, 'seen_movies', api_ver=2)
