from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import datetime

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

        if movie_year is not None and movie_year > datetime.datetime.now().year:
            log.debug('Skipping Blu-ray.com lookup since movie year is %s', movie_year)
            return

        log.debug('Searching Blu-ray.com for release date of {} ({})'.format(movie_name, movie_year))

        release_date = None
        try:
            with Session() as session:
                lookup = get_plugin_by_name('api_bluray').instance.lookup
                movie = lookup(title=movie_name, year=movie_year, session=session)
                if movie:
                    release_date = movie.release_date
        except LookupError as e:
            log.debug(e)
        if release_date:
            log.debug('received release date: {0}'.format(release_date))
        return release_date


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesMoviesBluray, 'est_movies_bluray', interfaces=['estimate_release'], api_ver=2)
