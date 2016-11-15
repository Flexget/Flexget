from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import options
from flexget.event import event
from flexget.terminal import console
from flexget.manager import Session

log = logging.getLogger('perftests')

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
    from flexget.plugins.metainfo.imdb_lookup import Movie
    from flexget.plugins.cli.performance import log_query_count
    from sqlalchemy.sql.expression import select
    from progressbar import ProgressBar, Percentage, Bar, ETA
    from sqlalchemy.orm import joinedload_all

    imdb_urls = []

    log.info('Getting imdb_urls ...')
    # query so that we avoid loading whole object (maybe cached?)
    for _, url in session.execute(select([Movie.id, Movie.url])):
        imdb_urls.append(url)
    log.info('Got %i urls from database' % len(imdb_urls))
    if not imdb_urls:
        log.info('so .. aborting')
        return

    # commence testing

    widgets = ['Benchmarking - ', ETA(), ' ', Percentage(), ' ', Bar(left='[', right=']')]
    bar = ProgressBar(widgets=widgets, maxval=len(imdb_urls)).start()

    log_query_count('test')
    start_time = time.time()
    for index, url in enumerate(imdb_urls):
        bar.update(index)

        # movie = session.query(Movie).filter(Movie.url == url).first()
        # movie = session.query(Movie).options(subqueryload(Movie.genres)).filter(Movie.url == url).one()

        movie = session.query(Movie). \
            options(joinedload_all(Movie.genres, Movie.languages,
                                   Movie.actors, Movie.directors)). \
            filter(Movie.url == url).first()

        # access it's members so they're loaded
        [x.name for x in movie.genres]
        [x.name for x in movie.directors]
        [x.name for x in movie.actors]
        [x.name for x in movie.languages]

    log_query_count('test')
    took = time.time() - start_time
    log.debug('Took %.2f seconds to query %i movies' % (took, len(imdb_urls)))


@event('options.register')
def register_parser_arguments():
    perf_parser = options.register_command('perf-test', cli_perf_test)
    perf_parser.add_argument('test_name', metavar='<test name>', choices=TESTS)
