from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestInputSites(FlexGetBase):

    __yaml__ = """
        tasks:
          test_rlslog:
            rlslog: http://www.rlslog.net/category/movies/dvdrip/
          test_scenereleases:
            scenereleases: http://sceper.eu/category/movies/movies-dvd-rip?themedemo=SceneRLSv3
          test_apple_trailers:
              apple_trailers: 480p
    """

    @attr(online=True)
    def test_rlslog(self):
        self.execute_task('test_rlslog')
        assert self.task.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_scenereleases(self):
        self.execute_task('test_scenereleases')
        assert self.task.entries, 'no entries created / site may be down'

    @attr(online=True)
    def test_apple_trailers(self):
        self.execute_task('test_apple_trailers')
        assert self.task.entries, 'no entries created / site may be down'
