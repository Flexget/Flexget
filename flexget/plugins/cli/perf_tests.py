from __future__ import unicode_literals, division, absolute_import
from argparse import SUPPRESS
from flexget.manager import Session
from flexget.plugin import register_plugin, register_parser_option
import logging

log = logging.getLogger('perftests')


class PerfTests(object):

    def on_process_start(self, task, config):
        test_name = task.manager.options.perf_test
        if test_name:
            task.manager.disable_tasks()
        else:
            return
        session = Session()
        try:
            if test_name == 'imdb_query':
                self.imdb_query(session)
            else:
                log.critical('Unknown performance test %s' % test_name)
        finally:
            session.close()

    def imdb_query(self, session):
        import time
        from flexget.plugins.metainfo.imdb_lookup import Movie
        from flexget.plugins.cli.performance import log_query_count
        from sqlalchemy.sql.expression import select
        from progressbar import ProgressBar, Percentage, Bar, ETA
        from sqlalchemy.orm import joinedload_all

        imdb_urls = []

        log.info('Getting imdb_urls ...')
        # query so that we avoid loading whole object (maybe cached?)
        for id, url in session.execute(select([Movie.id, Movie.url])):
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

            #movie = session.query(Movie).filter(Movie.url == url).first()
            #movie = session.query(Movie).options(subqueryload(Movie.genres)).filter(Movie.url == url).one()

            movie = session.query(Movie).\
                options(joinedload_all(Movie.genres, Movie.languages,
                Movie.actors, Movie.directors)).\
                filter(Movie.url == url).first()

            # access it's members so they're loaded
            var = [x.name for x in movie.genres]
            var = [x.name for x in movie.directors]
            var = [x.name for x in movie.actors]
            var = [x.name for x in movie.languages]

        log_query_count('test')
        took = time.time() - start_time
        log.debug('Took %.2f seconds to query %i movies' % (took, len(imdb_urls)))


register_plugin(PerfTests, 'perftests', api_ver=2, debug=True, builtin=True)
register_parser_option('--perf-test', action='store', dest='perf_test', default='',
                       help=SUPPRESS)
