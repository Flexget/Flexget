from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging

from flexget.plugin import register_plugin

log = logging.getLogger('est_movies')


class EstimatesReleasedMovies(object):

    def estimate(self, entry):
        if 'tmdb_released' in entry:
            log.verbose('Querying release estimation for %s' % entry['title'])
            return entry['tmdb_released']
        elif 'movie_year' in entry:
            return datetime(year=entry['movie_year'], month=1, day=1)
        else:
            log.debug('Unable to check release for %s, tmdb_release field is not defined' %
                      entry['title'])

register_plugin(EstimatesReleasedMovies, 'est_released_movies', groups=['estimate_release'])
