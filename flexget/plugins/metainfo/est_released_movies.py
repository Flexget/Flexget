from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('est_movies')


class EstimatesRelasedMovies(object):

    def estimate(self, entry):
        if 'tmdb_released' in entry:
            log.verbose('Checking %s' % entry['title'])
            try:
                return entry['tmdb_released'].date()
            except Exception as e:
                log.exception(e)
        else:
            log.warning('Unable to check release for %s, tmdb_release field is not defined' %
                        entry['title'])

register_plugin(EstimatesRelasedMovies, 'est_relased_movies', groups=['estimate_release'])
