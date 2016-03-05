from __future__ import unicode_literals, division, absolute_import

import pytest
from jinja2 import Template

from flexget.entry import Entry


class TestEmitSeries(object):
    _config = """
        templates:
          global:
            parsing:
              series: {{parser}}
              movie: {{parser}}
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
              from_start: yes
            series:
            - Test Series 3:
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

    @pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request):
        """Override and parametrize default config fixture."""
        return Template(self._config).render({'parser': request.param})

    def inject_series(self, execute_task, release_name):
        execute_task('inject_series', options={'inject': [Entry(title=release_name, url='')], 'disable_tracking': True})

    def test_emit_series_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 1 S02E01')
        task = execute_task('test_emit_series_backfill')
        assert task.find_entry(title='Test Series 1 S01E01')
        assert task.find_entry(title='Test Series 1 S02E02')
        task = execute_task('test_emit_series_backfill')
        assert task.find_entry(title='Test Series 1 S01E02')
        assert task.find_entry(title='Test Series 1 S02E03')
        self.inject_series(execute_task, 'Test Series 1 S02E08')
        task = execute_task('test_emit_series_backfill')
        assert task.find_entry(title='Test Series 1 S01E03')
        assert task.find_entry(title='Test Series 1 S02E04')
        assert task.find_entry(title='Test Series 1 S02E05')
        assert task.find_entry(title='Test Series 1 S02E06')
        assert task.find_entry(title='Test Series 1 S02E07')

    def test_emit_series_no_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 1 S01E01')
        self.inject_series(execute_task, 'Test Series 1 S01E05')
        task = execute_task('test_emit_series_no_backfill')
        assert len(task.all_entries) == 1
        assert task.find_entry(title='Test Series 1 S01E06')

    def test_emit_series_rejected(self, execute_task):
        self.inject_series(execute_task, 'Test Series 2 S01E03 720p')
        task = execute_task('test_emit_series_rejected')
        assert task.find_entry(title='Test Series 2 S01E01')
        assert task.find_entry(title='Test Series 2 S01E02')
        assert task.find_entry(title='Test Series 2 S01E03')

    def test_emit_series_from_start(self, execute_task):
        task = execute_task('test_emit_series_from_start')
        assert task.find_entry(title='Test Series 3 S01E01')
        task = execute_task('test_emit_series_from_start')
        assert task.find_entry(title='Test Series 3 S01E02')

    def test_emit_series_begin(self, execute_task):
        task = execute_task('test_emit_series_begin')
        assert task.find_entry(title='Test Series 4 S03E03')

    def test_emit_series_begin_and_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 5 S02E02')
        task = execute_task('test_emit_series_begin_and_backfill')
        # with backfill and begin, no backfilling should be done
        assert task.find_entry(title='Test Series 5 S03E02')
        assert len(task.all_entries) == 1

    def test_emit_series_begin_backfill_and_rerun(self, execute_task):
        self.inject_series(execute_task, 'Test Series 6 S03E01')
        task = execute_task('test_emit_series_begin_backfill_and_rerun')
        # with backfill and begin, no backfilling should be done
        assert task._rerun_count == 1
        assert task.find_entry(title='Test Series 6 S03E03')
        assert len(task.all_entries) == 1
        assert len(task.mock_output) == 2 # Should have S03E02 and S03E03

    def test_emit_series_backfill_advancement(self, execute_task):
        self.inject_series(execute_task, 'Test Series 7 S02E01')
        task = execute_task('test_emit_series_backfill_advancement')
        assert task._rerun_count == 1
        assert len(task.all_entries) == 1
        assert task.find_entry('rejected', title='Test Series 7 S03E01')

    def test_emit_series_advancement(self, execute_task):
        self.inject_series(execute_task, 'Test Series 8 S01E01')
        task = execute_task('test_emit_series_advancement')
        assert task._rerun_count == 1
        assert len(task.all_entries) == 1
        assert task.find_entry('rejected', title='Test Series 8 S02E01')

    def test_emit_series_alternate_name(self, execute_task):
        task = execute_task('test_emit_series_alternate_name')
        assert len(task.mock_output) == 1
        # There should be 2 alternate names
        assert len(task.mock_output[0].get('series_alternate_names')) == 2
        assert ['Testing Series 8', 'Tests Series 8'].sort() == \
               task.mock_output[0].get('series_alternate_names').sort(), 'Alternate names do not match (how?).'

    def test_emit_series_alternate_name_duplicates(self, execute_task):
        task = execute_task('test_emit_series_alternate_name_duplicates')
        assert len(task.mock_output) == 1
        # duplicate alternate names should only result in 1
        # even if it is not a 'complete match' (eg. My Show == My SHOW)
        assert len(task.mock_output[0].get('series_alternate_names')) == 1, 'Duplicate alternate names.'

    def test_emit_series_search_strings(self, execute_task):
        # This test makes sure that the number of search strings increases when the amount of alt names increases.
        task = execute_task('test_emit_series_alternate_name_duplicates')
        s1 = len(task.mock_output[0].get('search_strings'))
        task = execute_task('test_emit_series_alternate_name')
        s2 = len(task.mock_output[0].get('search_strings'))
        assert s2 > s1, 'Alternate names did not create sufficient search strings.'

