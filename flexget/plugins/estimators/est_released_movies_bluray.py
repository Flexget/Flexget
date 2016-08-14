from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name
from flexget.utils.database import Session


log = logging.getLogger('est_movies_bluray')


class EstimatesMoviesBluray(object):

    @plugin.priority(2)
    def estimate(self, entry):
        if 'movie_name' not in entry:
            return

        movie_name = entry['movie_name']
        movie_year = entry.get('movie_year')

        log.debug('Searching Blu-ray.com for release date of {} ({})'.format(movie_name, movie_year))

        try:
            with Session() as session:
                lookup = get_plugin_by_name('api_bluray').instance.lookup
                movie = lookup(title=movie_name, year=movie_year, session=session)
        except LookupError as e:
            log.debug(e)
            return
        if movie and movie.release_date:
            log.debug('received release date: {0}'.format(movie.release_date))
            return movie.release_date


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesMoviesBluray, 'est_movies_bluray', groups=['estimate_release'], api_ver=2)
