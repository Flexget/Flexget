from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.entry import Entry


#TODO Add more standard tests
class TestNextSeriesSeasonSeasonsPack(object):
    _config = """
        templates:
          global:
            parsing:
              series: internal
        tasks:
          inject_series:
            series:
              - Test Series 1:
                  season_packs: always
              - Test Series 2:
                  season_packs: always
              - Test Series 3:
                  season_packs: always
              - Test Series 4:
                  season_packs: always
              - Test Series 5:
                  season_packs: always
              - Test Series 6:
                  season_packs: always
              - Test Series 7:
                  season_packs: always
          test_next_series_seasons:
            next_series_seasons: yes
            series:
            - Test Series 1:
                identified_by: ep
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
          test_next_series_seasons_ep_history:
            next_series_seasons: yes
            series:
            - Test Series 2:
                identified_by: ep
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
          test_next_series_seasons_backfill:
            next_series_seasons:
              backfill: yes
            series:
            - Test Series 3:
                identified_by: ep
                tracking: backfill
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
          test_next_series_seasons_ep_history_backfill:
            next_series_seasons:
              backfill: yes
            series:
            - Test Series 4:
                identified_by: ep
                tracking: backfill
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
          test_next_series_seasons_backfill_and_begin:
            next_series_seasons:
              backfill: yes
            series:
            - Test Series 5:
                identified_by: ep
                tracking: backfill
                begin: S02E01
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
          test_next_series_seasons_ep_history_backfill_and_begin:
            next_series_seasons:
              backfill: yes
            series:
            - Test Series 6:
                identified_by: ep
                tracking: backfill
                begin: S02E01
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
          test_next_series_seasons_from_start:
            next_series_seasons:
                from_start: yes
            series:
            - Test Series 7:
                identified_by: ep
                season_packs:
                    threshold: 1000
                    reject_eps: yes
            max_reruns: 0
    """

    @pytest.fixture()
    def config(self):
        """Season packs aren't supported by guessit yet."""
        return self._config

    def inject_series(self, execute_task, release_name):
        execute_task('inject_series', options={'inject': [Entry(title=release_name, url='')], 'disable_tracking': True})

    @pytest.mark.parametrize("task_name,inject,result_find,result_length", [
        ('test_next_series_seasons',
            ['Test Series 1 S02'],
            ['Test Series 1 S03'],
            1),
        ('test_next_series_seasons_ep_history',
            ['Test Series 2 S02', 'Test Series 2 S03E01'],
            ['Test Series 2 S03'],
            1),
        ('test_next_series_seasons_backfill',
            ['Test Series 3 S02'],
            ['Test Series 3 S01', 'Test Series 3 S03'],
            2),
        ('test_next_series_seasons_ep_history_backfill',
            ['Test Series 4 S02', 'Test Series 4 S03E01'],
            ['Test Series 4 S01', 'Test Series 4 S03'],
            2),
        ('test_next_series_seasons_backfill_and_begin',
            ['Test Series 5 S02'],
            ['Test Series 5 S03'],
            1),
        ('test_next_series_seasons_ep_history_backfill_and_begin',
            ['Test Series 6 S02', 'Test Series 6 S03E01'],
            ['Test Series 6 S03'],
            1)
    ])
    def test_next_series_seasons(self, execute_task, task_name, inject, result_find, result_length):
        for entity_id in inject:
            self.inject_series(execute_task, entity_id)
        task = execute_task(task_name)
        for result_title in result_find:
            assert task.find_entry(title=result_title)
        assert len(task.all_entries) == result_length

    # Tests which require multiple tasks to be executed in order
    # Each run_parameter is a tuple of lists: [task name, list of series ID(s) to inject, list of result(s) to find]
    @pytest.mark.parametrize("run_parameters", [
        (
         ['test_next_series_seasons_from_start',
            [],
            ['Test Series 7 S01']],
         ['test_next_series_seasons_from_start',
            [],
            ['Test Series 7 S02']]
        )
    ])
    def test_next_series_seasons_multirun(self, execute_task, run_parameters):
        for this_test in run_parameters:
            for entity_id in this_test[1]:
                self.inject_series(execute_task, entity_id)
            task = execute_task(this_test[0])
            for result_title in this_test[2]:
                assert task.find_entry(title=result_title)
            assert len(task.all_entries) == len(this_test[2])
