from __future__ import unicode_literals, division, absolute_import

from nose.plugins.attrib import attr

from tests import FlexGetBase


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

    @attr(online=True)
    def test_rlslog(self):
        self.execute_task('test_rlslog')
        assert self.task.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_sceper(self):
        self.execute_task('test_sceper')
        assert self.task.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_apple_trailers(self):
        self.execute_task('test_apple_trailers')
        assert self.task.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_apple_trailers_simple(self):
        self.execute_task('test_apple_trailers_simple')
        assert self.task.entries, 'no entries created / site may be down'
