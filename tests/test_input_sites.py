from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, use_vcr


class TestInputSites(object):

    config = """
        tasks:
          test_rlslog:
            rlslog: http://www.rlslog.net/category/movies/dvdrip/
          test_sceper:
            sceper: http://sceper.ws/category/movies/movies-dvd-rip
          test_apple_trailers:
            apple_trailers:
              quality: 480p
              genres: ['Action and Adventure']
          test_apple_trailers_simple:
            apple_trailers: 720p

    """

    @use_vcr
    def test_rlslog(self, execute_task):
        task = execute_task('test_rlslog')
        assert task.entries, 'no entries created / site may be down'

    @use_vcr
    def test_sceper(self, execute_task):
        task = execute_task('test_sceper')
        assert task.entries, 'no entries created / site may be down'

    @use_vcr
    def test_apple_trailers(self, execute_task):
        task = execute_task('test_apple_trailers')
        assert task.entries, 'no entries created / site may be down'

    @use_vcr
    def test_apple_trailers_simple(self, execute_task):
        task = execute_task('test_apple_trailers_simple')
        assert task.entries, 'no entries created / site may be down'
