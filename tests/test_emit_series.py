from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, build_parser_function
from flexget.entry import Entry


class BaseEmitSeries(FlexGetBase):
    __yaml__ = """
        tasks:
          inject_series:
            series:
              - Test Series 1
              - Test Series 2:
                  quality: 1080p
              - Test Series 3
              - Test Series 4
              - Test Series 5
              - Test Series 6
              - Test Series 7
              - Test Series 8
          test_emit_series_backfill:
            emit_series:
              backfill: yes
            series:
            - Test Series 1:
                tracking: backfill
                identified_by: ep
            rerun: 0
          test_emit_series_no_backfill:
            emit_series: yes
            series:
            - Test Series 1
            rerun: 0
          test_emit_series_rejected:
            emit_series:
              backfill: yes
            series:
            - Test Series 2:
                tracking: backfill
                identified_by: ep
            rerun: 0
          test_emit_series_from_start:
            emit_series:
              backfill: yes
            series:
            - Test Series 3:
                from_start: yes
                identified_by: ep
            rerun: 0
          test_emit_series_begin:
            emit_series: yes
            series:
            - Test Series 4:
                begin: S03E03
                identified_by: ep
            rerun: 0
          test_emit_series_begin_and_backfill:
            emit_series:
              backfill: yes
            series:
            - Test Series 5:
                begin: S03E02
                tracking: backfill
            rerun: 0
          test_emit_series_begin_backfill_and_rerun:
            accept_all: yes  # make sure mock output stores all created entries
            emit_series:
              backfill: yes
            series:
            - Test Series 6:
                begin: S03E02
                tracking: backfill
            mock_output: yes
            rerun: 1
          test_emit_series_backfill_advancement:
            emit_series:
              backfill: yes
            series:
            - Test Series 7:
                identified_by: ep
                tracking: backfill
            regexp:
              reject:
              - .
          test_emit_series_advancement:
            emit_series: yes
            series:
            - Test Series 8:
                identified_by: ep
            regexp:
              reject:
              - .
          test_emit_series_alternate_name:
            emit_series: yes
            series:
            - Test Series 8:
               begin: S01E01
               alternate_name:
                 - Testing Series 8
                 - Tests Series 8
            rerun: 0
            mock_output: yes
          test_emit_series_alternate_name_duplicates:
            emit_series: yes
            series:
            - Test Series 8:
               begin: S01E01
               alternate_name:
                 - Testing Series 8
                 - Testing SerieS 8
            rerun: 0
            mock_output: yes
    """

    def inject_series(self, release_name):
        self.execute_task('inject_series', options = {'inject': [Entry(title=release_name, url='')], 'disable_tracking': True})

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

    def test_emit_series_no_backfill(self):
        self.inject_series('Test Series 1 S01E01')
        self.inject_series('Test Series 1 S01E05')
        self.execute_task('test_emit_series_no_backfill')
        assert len(self.task.all_entries) == 1
        assert self.task.find_entry(title='Test Series 1 S01E06')

    def test_emit_series_rejected(self):
        self.inject_series('Test Series 2 S01E03 720p')
        self.execute_task('test_emit_series_rejected')
        assert self.task.find_entry(title='Test Series 2 S01E01')
        assert self.task.find_entry(title='Test Series 2 S01E02')
        assert self.task.find_entry(title='Test Series 2 S01E03')

    def test_emit_series_from_start(self):
        self.inject_series('Test Series 3 S01E03')
        self.execute_task('test_emit_series_from_start')
        assert self.task.find_entry(title='Test Series 3 S01E01')
        assert self.task.find_entry(title='Test Series 3 S01E02')
        assert self.task.find_entry(title='Test Series 3 S01E04')
        self.execute_task('test_emit_series_from_start')
        assert self.task.find_entry(title='Test Series 3 S01E05')

    def test_emit_series_begin(self):
        self.execute_task('test_emit_series_begin')
        assert self.task.find_entry(title='Test Series 4 S03E03')

    def test_emit_series_begin_and_backfill(self):
        self.inject_series('Test Series 5 S02E02')
        self.execute_task('test_emit_series_begin_and_backfill')
        # with backfill and begin, no backfilling should be done
        assert self.task.find_entry(title='Test Series 5 S03E02')
        assert len(self.task.all_entries) == 1

    def test_emit_series_begin_backfill_and_rerun(self):
        self.inject_series('Test Series 6 S03E01')
        self.execute_task('test_emit_series_begin_backfill_and_rerun')
        # with backfill and begin, no backfilling should be done
        assert self.task._rerun_count == 1
        assert self.task.find_entry(title='Test Series 6 S03E03')
        assert len(self.task.all_entries) == 1
        assert len(self.task.mock_output) == 2 # Should have S03E02 and S03E03

    def test_emit_series_backfill_advancement(self):
        self.inject_series('Test Series 7 S02E01')
        self.execute_task('test_emit_series_backfill_advancement')
        assert self.task._rerun_count == 1
        assert len(self.task.all_entries) == 1
        assert self.task.find_entry('rejected', title='Test Series 7 S03E01')

    def test_emit_series_advancement(self):
        self.inject_series('Test Series 8 S01E01')
        self.execute_task('test_emit_series_advancement')
        assert self.task._rerun_count == 1
        assert len(self.task.all_entries) == 1
        assert self.task.find_entry('rejected', title='Test Series 8 S02E01')

    def test_emit_series_alternate_name(self):
        self.execute_task('test_emit_series_alternate_name')
        assert len(self.task.mock_output) == 1
        # There should be 2 alternate names
        assert len(self.task.mock_output[0].get('series_alternate_names')) == 2
        assert ['Testing Series 8', 'Tests Series 8'].sort() == \
               self.task.mock_output[0].get('series_alternate_names').sort(), 'Alternate names do not match (how?).'

    def test_emit_series_alternate_name_duplicates(self):
        self.execute_task('test_emit_series_alternate_name_duplicates')
        assert len(self.task.mock_output) == 1
        # duplicate alternate names should only result in 1
        # even if it is not a 'complete match' (eg. My Show == My SHOW)
        assert len(self.task.mock_output[0].get('series_alternate_names')) == 1, 'Duplicate alternate names.'

    def test_emit_series_search_strings(self):
        # This test makes sure that the number of search strings increases when the amount of alt names increases.
        self.execute_task('test_emit_series_alternate_name_duplicates')
        s1 = len(self.task.mock_output[0].get('search_strings'))
        self.execute_task('test_emit_series_alternate_name')
        s2 = len(self.task.mock_output[0].get('search_strings'))
        assert s2 > s1, 'Alternate names did not create sufficient search strings.'

class TestGuessitEmitSeries(BaseEmitSeries):
    def __init__(self):
        super(TestGuessitEmitSeries, self).__init__()
        self.add_tasks_function(build_parser_function('guessit'))


class TestInternalEmitSeries(BaseEmitSeries):
    def __init__(self):
        super(TestInternalEmitSeries, self).__init__()
        self.add_tasks_function(build_parser_function('internal'))
