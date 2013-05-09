from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('est_movies')


class EstimatesRelasedMovies(object):

    def is_released(self, task, entry):
        if ('tmdb_released' in entry):
            log.info("Checking %s " % entry['title'])
            try:
                return entry['tmdb_released'].date()
            except:
                return None
        return None

register_plugin(EstimatesRelasedMovies, 'est_relased_movies', groups=['estimate_released'])
