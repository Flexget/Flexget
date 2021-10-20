from loguru import logger

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import console

logger = logger.bind(name='perftests')

TESTS = ['imdb_query']


def cli_perf_test(manager, options):
    if options.test_name not in TESTS:
        console('Unknown performance test %s' % options.test_name)
        return
    session = Session()
    try:
        if options.test_name == 'imdb_query':
            imdb_query(session)
    finally:
        session.close()


def imdb_query(session):
    import time

    from rich.progress import track
    from sqlalchemy.orm import joinedload
    from sqlalchemy.sql.expression import select

    # NOTE: importing other plugins directly is discouraged
    from flexget.components.imdb.db import Movie
    from flexget.plugins.cli.performance import log_query_count

    imdb_urls = []

    logger.info('Getting imdb_urls ...')
    # query so that we avoid loading whole object (maybe cached?)
    for _, url in session.execute(select([Movie.id, Movie.url])):
        imdb_urls.append(url)
    logger.info('Got {} urls from database', len(imdb_urls))
    if not imdb_urls:
        logger.info('so .. aborting')
        return

    # commence testing

    log_query_count('test')
    start_time = time.time()
    for url in track(imdb_urls, description='Benchmarking...'):

        # movie = session.query(Movie).filter(Movie.url == url).first()
        # movie = session.query(Movie).options(subqueryload(Movie.genres)).filter(Movie.url == url).one()

        movie = (
            session.query(Movie)
            .options(
                joinedload(Movie.genres),
                joinedload(Movie.languages),
                joinedload(Movie.actors),
                joinedload(Movie.directors),
            )
            .filter(Movie.url == url)
            .first()
        )

        # access it's members so they're loaded
        [x.name for x in movie.genres]
        [x.name for x in movie.directors]
        [x.name for x in movie.actors]
        [x.language for x in movie.languages]

    log_query_count('test')
    took = time.time() - start_time
    logger.debug('Took %.2f seconds to query %i movies' % (took, len(imdb_urls)))


@event('options.register')
def register_parser_arguments():
    perf_parser = options.register_command('perf-test', cli_perf_test)
    perf_parser.add_argument('test_name', metavar='<test name>', choices=TESTS)
