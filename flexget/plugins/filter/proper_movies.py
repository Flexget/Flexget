from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Unicode
from sqlalchemy.schema import Index
from sqlalchemy.sql.expression import desc

from flexget import plugin
from flexget.event import event, fire_event
from flexget.manager import Base
from flexget.utils.log import log_once
from flexget.utils.tools import parse_timedelta

logger = logger.bind(name='proper_movies')


class ProperMovie(Base):
    __tablename__ = 'proper_movies'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    task = Column('feed', Unicode)
    imdb_id = Column(String, index=True)
    quality = Column(String)
    proper_count = Column(Integer)
    added = Column(DateTime)

    def __init__(self):
        self.added = datetime.now()

    def __repr__(self):
        return '<ProperMovie(title=%s,task=%s,imdb_id=%s,quality=%s,proper_count=%s,added=%s)>' % (
            self.title,
            self.task,
            self.imdb_id,
            self.quality,
            self.proper_count,
            self.added,
        )


# create index
columns = Base.metadata.tables['proper_movies'].c
Index(
    'proper_movies_imdb_id_quality_proper', columns.imdb_id, columns.quality, columns.proper_count
)


class FilterProperMovies:
    """
        Automatically download proper movies.

        Configuration:

            proper_movies: n <minutes|hours|days|weeks>

        or permanently:

            proper_movies: yes

        Value no will disable plugin.
    """

    schema = {'oneOf': [{'type': 'boolean'}, {'type': 'string', 'format': 'interval'}]}

    def on_task_filter(self, task, config):
        logger.debug('check for enforcing')

        # parse config
        if isinstance(config, bool):
            # configured a boolean false, disable plugin
            if not config:
                return
            # configured a boolean true, disable timeframe
            timeframe = None
        else:
            # parse time window
            logger.debug('interval: {}', config)
            try:
                timeframe = parse_timedelta(config)
            except ValueError:
                raise plugin.PluginError('Invalid time format', logger)

        # throws DependencyError if not present aborting task
        imdb_lookup = plugin.get_plugin_by_name('imdb_lookup').instance

        for entry in task.entries:
            parser = plugin.get('parsing', self).parse_movie(entry['title'])

            # if we have imdb_id already evaluated
            if entry.get('imdb_id', None, eval_lazy=False) is None:
                try:
                    # TODO: fix imdb_id_lookup, cumbersome that it returns None and or throws exception
                    # Also it's crappy name!
                    imdb_id = imdb_lookup.imdb_id_lookup(
                        movie_title=parser.name, movie_year=parser.year, raw_title=entry['title']
                    )
                    if imdb_id is None:
                        continue
                    entry['imdb_id'] = imdb_id
                except plugin.PluginError as pe:
                    log_once(pe.value)
                    continue

            quality = parser.quality.name

            logger.debug('quality: {}', quality)
            logger.debug('imdb_id: {}', entry['imdb_id'])
            logger.debug('current proper count: {}', parser.proper_count)

            proper_movie = (
                task.session.query(ProperMovie)
                .filter(ProperMovie.imdb_id == entry['imdb_id'])
                .filter(ProperMovie.quality == quality)
                .order_by(desc(ProperMovie.proper_count))
                .first()
            )

            if not proper_movie:
                logger.debug('no previous download recorded for {}', entry['imdb_id'])
                continue

            highest_proper_count = proper_movie.proper_count
            logger.debug('highest_proper_count: {}', highest_proper_count)

            accept_proper = False
            if parser.proper_count > highest_proper_count:
                logger.debug('proper detected: {} ', proper_movie)

                if timeframe is None:
                    accept_proper = True
                else:
                    expires = proper_movie.added + timeframe
                    logger.debug('propers timeframe: {}', timeframe)
                    logger.debug('added: {}', proper_movie.added)
                    logger.debug('propers ignore after: {}', str(expires))
                    if datetime.now() < expires:
                        accept_proper = True
                    else:
                        logger.verbose("Proper `{}` has past it's expiration time", entry['title'])

            if accept_proper:
                logger.info(
                    'Accepting proper version previously downloaded movie `{}`', entry['title']
                )
                # TODO: does this need to be called?
                # fire_event('forget', entry['imdb_url'])
                fire_event('forget', entry['imdb_id'])
                entry.accept('proper version of previously downloaded movie')

    def on_task_learn(self, task, config):
        """Add downloaded movies to the database"""
        logger.debug('check for learning')
        for entry in task.accepted:
            if 'imdb_id' not in entry:
                logger.debug('`{}` does not have imdb_id', entry['title'])
                continue

            parser = plugin.get('parsing', self).parse_movie(entry['title'])

            quality = parser.quality.name

            logger.debug('quality: {}', quality)
            logger.debug('imdb_id: {}', entry['imdb_id'])
            logger.debug('proper count: {}', parser.proper_count)

            proper_movie = (
                task.session.query(ProperMovie)
                .filter(ProperMovie.imdb_id == entry['imdb_id'])
                .filter(ProperMovie.quality == quality)
                .filter(ProperMovie.proper_count == parser.proper_count)
                .first()
            )

            if not proper_movie:
                pm = ProperMovie()
                pm.title = entry['title']
                pm.task = task.name
                pm.imdb_id = entry['imdb_id']
                pm.quality = quality
                pm.proper_count = parser.proper_count
                task.session.add(pm)
                logger.debug('added {}', pm)
            else:
                logger.debug('{} already exists', proper_movie)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterProperMovies, 'proper_movies', api_ver=2)
