from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, use_vcr


class TestInputSites(FlexGetBase):

    __yaml__ = """
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
    def test_rlslog(self):
        self.execute_task('test_rlslog')
        assert self.task.entries, 'no entries created / site may be down'

    @use_vcr
    def test_sceper(self):
        self.execute_task('test_sceper')
        assert self.task.entries, 'no entries created / site may be down'

    @use_vcr
    def test_apple_trailers(self):
        self.execute_task('test_apple_trailers')
        assert self.task.entries, 'no entries created / site may be down'

    @use_vcr
    def test_apple_trailers_simple(self):
        self.execute_task('test_apple_trailers_simple')
        assert self.task.entries, 'no entries created / site may be down'
