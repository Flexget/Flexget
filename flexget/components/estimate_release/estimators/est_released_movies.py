from datetime import datetime

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='est_movies')


class EstimatesReleasedMovies:
    @plugin.priority(0)
    def estimate(self, entry):
        if 'tmdb_released' in entry:
            logger.verbose('Querying release estimation for {}', entry['title'])
            return entry['tmdb_released']
        elif 'movie_year' in entry and entry['movie_year'] is not None:
            try:
                return datetime(year=entry['movie_year'], month=1, day=1)
            except ValueError:
                pass
        logger.debug(
            'Unable to check release for {}, tmdb_release and movie_year fields are not defined',
            entry['title'],
        )


@event('plugin.register')
def register_plugin():
    plugin.register(
        EstimatesReleasedMovies, 'est_released_movies', interfaces=['estimate_release'], api_ver=2
    )
