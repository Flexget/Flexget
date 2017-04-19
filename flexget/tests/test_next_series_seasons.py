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
          test_next_series_seasons_season_pack:
            next_series_seasons: yes
            series:
            - Test Series 1:
                identified_by: ep
                season_packs: only
            max_reruns: 0
          test_next_series_seasons_season_pack_backfill:
            next_series_seasons:
              backfill: yes
            series:
            - Test Series 2:
                identified_by: ep
                tracking: backfill
                season_packs: only
            max_reruns: 0
    """

    @pytest.fixture()
    def config(self):
        """Season packs aren't supported by guessit yet."""
        return self._config

    def inject_series(self, execute_task, release_name):
        execute_task('inject_series', options={'inject': [Entry(title=release_name, url='')], 'disable_tracking': True})

    def test_next_series_seasons_season_pack(self, execute_task):
        self.inject_series(execute_task, 'Test Series 1 S02')
        task = execute_task('test_next_series_seasons_season_pack')
        assert task.find_entry(title='Test Series 1 S03')
        assert len(task.all_entries) == 1

    def test_next_series_seasons_season_pack_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 2 S02')
        task = execute_task('test_next_series_seasons_season_pack_backfill')
        assert task.find_entry(title='Test Series 2 S01')
        assert task.find_entry(title='Test Series 2 S03')
        assert len(task.all_entries) == 2
