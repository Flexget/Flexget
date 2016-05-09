from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from collections import defaultdict

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
    schema = {
        'oneOf': [
            {'type': 'string', 'enum': ['strict', 'loose']},
            {
                'type': 'object',
                'properties': {
                    'scope': {'type': 'string', 'enum': ['global', 'local']},
                    'matching': {'type': 'string', 'enum': ['strict', 'loose']}
                },
                'additionalProperties': False
            }
        ]
    }

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['imdb_id', 'tmdb_id', 'trakt_movie_id']
        self.keyword = 'seen_movies'

    # We run last (-255) to make sure we don't reject duplicates before all the other plugins get a chance to reject.
    @plugin.priority(-255)
    def on_task_filter(self, task, config):
        if not isinstance(config, dict):
            config = {'matching': config}
        # Reject all entries without
        if config.get('matching') == 'strict':
            for entry in task.entries:
                if not any(field in entry for field in self.fields):
                    log.info('Rejecting %s because of missing movie (imdb, tmdb or trakt) id' % entry['title'])
                    entry.reject('missing movie (imdb, tmdb or trakt) id, strict')
        # call super
        super(FilterSeenMovies, self).on_task_filter(task, config.get('scope', True))
        # check that two copies of a movie have not been accepted this run
        accepted_ids = defaultdict(set)
        for entry in task.accepted:
            for field in self.fields:
                if field in entry:
                    if entry[field] in accepted_ids[field]:
                        entry.reject('already accepted %s %s once in task' % (field, entry[field]))
                        break
                    else:
                        accepted_ids[field].add(entry[field])

    def on_task_learn(self, task, config):
        if not isinstance(config, dict):
            config = {'matching': config}
        # call super
        super(FilterSeenMovies, self).on_task_learn(task, config.get('scope', True))

@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeenMovies, 'seen_movies', api_ver=2)
