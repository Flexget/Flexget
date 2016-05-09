from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from datetime import datetime
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('est_movies')


class EstimatesReleasedMovies(object):

    def estimate(self, entry):
        if 'tmdb_released' in entry:
            log.verbose('Querying release estimation for %s' % entry['title'])
            return entry['tmdb_released']
        elif 'movie_year' in entry:
            try:
                return datetime(year=entry['movie_year'], month=1, day=1)
            except ValueError:
                pass
        log.debug('Unable to check release for %s, tmdb_release field is not defined' % entry['title'])


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesReleasedMovies, 'est_released_movies', groups=['estimate_release'], api_ver=2)
