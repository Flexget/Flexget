from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin
from datetime import datetime

log = logging.getLogger('est_movies')


class EstimatesRelasedMovies(object):

    def is_released(self, task, entry):
        if ('tmdb_released' in entry):
            log.info("Checking %s " % entry['title'])
            now = datetime.now()
            try:
                if now.date() < entry['tmdb_released'].date():
                    log.debug("title hasn't aired yet : air %s" % (entry['tmdb_released'].date()))
                    return False, entry['tmdb_released'].date()
            except:
                return None, None
            return True, entry['tmdb_released'].date()
        return None, None

register_plugin(EstimatesRelasedMovies, 'est_relased_movies', groups=['estimate_released'])
