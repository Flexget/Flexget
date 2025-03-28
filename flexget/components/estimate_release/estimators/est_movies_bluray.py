import datetime

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.database import Session

logger = logger.bind(name='est_movies_bluray')


class EstimatesMoviesBluray:
    @plugin.priority(2)
    def estimate(self, entry):
        if 'movie_name' not in entry:
            return None

        movie_name = entry['movie_name']
        movie_year = entry.get('movie_year')

        if movie_year is not None and movie_year > datetime.datetime.now().year:
            logger.debug('Skipping Blu-ray.com lookup since movie year is {}', movie_year)
            return None

        logger.debug('Searching Blu-ray.com for release date of {} ({})', movie_name, movie_year)

        entity_data = {'data_exists': True, 'entity_date': None}
        try:
            with Session() as session:
                lookup = plugin.get('api_bluray', self).lookup
                movie = lookup(title=movie_name, year=movie_year, session=session)
                if movie:
                    entity_data['entity_date'] = movie.release_date
        except LookupError as e:
            logger.debug(e)
            entity_data['data_exists'] = False
        if entity_data['entity_date']:
            logger.debug('received release date: {}', entity_data['entity_date'])
        return entity_data


@event('plugin.register')
def register_plugin():
    plugin.register(
        EstimatesMoviesBluray, 'est_movies_bluray', interfaces=['estimate_release'], api_ver=2
    )
