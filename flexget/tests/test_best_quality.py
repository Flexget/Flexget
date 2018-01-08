from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


class TestBestQuality(object):
    config = """
        tasks:
          best_accept:
            best_quality:
              on_best: accept
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          best_allow:
            best_quality:
              on_best: allow
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
          lower_allow:
            best_quality:
              on_lower: allow
            mock:
              - {title: 'Movie.720p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
              - {title: 'Movie.1080p.WEB-DL.X264.AC3-GRP1', 'id': 'Movie'}
    """

    def test_best_accept(self, execute_task):
        task = execute_task('best_accept')
        entry = task.find_entry('accepted', title='Movie.1080p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.1080p.WEB-DL.X264.AC3-GRP1 should be accepted'
        entry = task.find_entry('rejected', title='Movie.720p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3-GRP1 should be rejected'

    def test_best_allow(self, execute_task):
        task = execute_task('best_allow')
        entry = task.find_entry('undecided', title='Movie.1080p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.1080p.WEB-DL.X264.AC3-GRP1 should be undecided'
        entry = task.find_entry('rejected', title='Movie.720p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3-GRP1 should be rejected'

    def test_lower_allow(self, execute_task):
        task = execute_task('lower_allow')
        entry = task.find_entry('undecided', title='Movie.1080p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.1080p.WEB-DL.X264.AC3-GRP1 should be undecided'
        entry = task.find_entry('undecided', title='Movie.720p.WEB-DL.X264.AC3-GRP1')
        assert entry, 'Movie.720p.WEB-DL.X264.AC3-GRP1 should be undecided'
