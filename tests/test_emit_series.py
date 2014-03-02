from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase
from flexget.entry import Entry


class TestEmitSeries(FlexGetBase):
    __yaml__ = """
        tasks:
          inject_series:
            series:
              - Test Series 1
              - Test Series 2:
                  quality: 1080p
          test_emit_series_backfill:
            emit_series:
              backfill: yes
            series:
            - Test Series 1:
                allow_backfill: yes
                identified_by: ep
            rerun: 0
          test_emit_series_rejected:
            emit_series:
              backfill: yes
            series:
            - Test Series 2:
                allow_backfill: yes
                identified_by: ep
            rerun: 0
    """

    def inject_series(self, release_name):
        self.execute_task('inject_series', options = {'inject': [Entry(title=release_name, url='')]})

    def test_emit_series_backfill(self):
        self.inject_series('Test Series 1 S02E01')
        self.execute_task('test_emit_series_backfill')
        assert self.task.find_entry(title='Test Series 1 S01E01')
        assert self.task.find_entry(title='Test Series 1 S02E02')
        self.execute_task('test_emit_series_backfill')
        assert self.task.find_entry(title='Test Series 1 S01E02')
        assert self.task.find_entry(title='Test Series 1 S02E03')
        self.inject_series('Test Series 1 S02E08')
        self.execute_task('test_emit_series_backfill')
        assert self.task.find_entry(title='Test Series 1 S01E03')
        assert self.task.find_entry(title='Test Series 1 S02E04')
        assert self.task.find_entry(title='Test Series 1 S02E05')
        assert self.task.find_entry(title='Test Series 1 S02E06')
        assert self.task.find_entry(title='Test Series 1 S02E07')

    def test_emit_series_rejected(self):
        self.inject_series('Test Series 2 S01E03 720p')
        self.execute_task('test_emit_series_rejected')
        assert self.task.find_entry(title='Test Series 2 S01E01')
        assert self.task.find_entry(title='Test Series 2 S01E02')
        assert self.task.find_entry(title='Test Series 2 S01E03')
