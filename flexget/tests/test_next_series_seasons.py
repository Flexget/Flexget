import pytest

from flexget.entry import Entry


# TODO Add more standard tests
class TestNextSeriesSeasonSeasonsPack:
    _config = """
        templates:
          global:
            parsing:
              series: internal
          anchors:
            _nss_backfill: &nss_backfill
              next_series_seasons:
                backfill: yes
            _nss_from_start: &nss_from_start
              next_series_seasons:
                from_start: yes
            _nss_backfill_from_start: &nss_backfill_from_start
              next_series_seasons:
                backfill: yes
                from_start: yes
            _series_ep_pack: &series_ep_pack
              identified_by: ep
              season_packs:
                threshold: 1000
                reject_eps: yes
            _series_ep_tracking_pack: &series_ep_tracking_pack
              identified_by: ep
              season_packs:
                threshold: 1000
                reject_eps: yes
            _series_ep_tracking_begin_s02e01: &series_ep_tracking_pack_begin_s02e01
              identified_by: ep
              begin: s02e01
              season_packs:
                threshold: 1000
                reject_eps: yes
            _series_ep_tracking_begin_s04e01: &series_ep_tracking_pack_begin_s04e01
              identified_by: ep
              begin: s04e01
              season_packs:
                threshold: 1000
                reject_eps: yes
        tasks:
          inject_series:
            series:
              settings:
                test_series:
                  season_packs: always
              test_series:
              - Test Series 1
              - Test Series 2
              - Test Series 3
              - Test Series 4
              - Test Series 5
              - Test Series 6
              - Test Series 7
              - Test Series 8
              - Test Series 9
              - Test Series 10
              - Test Series 11
              - Test Series 12
              - Test Series 13
              - Test Series 14
              - Test Series 15
              - Test Series 16
              - Test Series 17
              - Test Series 18
              - Test Series 19
              - Test Series 20
              - Test Series 21
              - Test Series 22
              - Test Series 23
              - Test Series 24
              - Test Series 25
              - Test Series 50
              - Test Series 100
          test_next_series_seasons_season_pack:
            next_series_seasons: yes
            series:
            - Test Series 1:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_backfill:
            <<: *nss_backfill
            series:
            - Test Series 2:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_backfill_and_begin:
            <<: *nss_backfill
            series:
            - Test Series 3:
                <<: *series_ep_tracking_pack_begin_s02e01
            max_reruns: 0
          test_next_series_seasons_season_pack_from_start:
            <<: *nss_from_start
            series:
            - Test Series 4:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_from_start_backfill:
            <<: *nss_backfill_from_start
            series:
            - Test Series 5:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_from_start_backfill_and_begin:
            <<: *nss_backfill_from_start
            series:
            - Test Series 6:
                <<: *series_ep_tracking_pack_begin_s02e01
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep:
            next_series_seasons: yes
            series:
            - Test Series 7:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_backfill:
            <<: *nss_backfill
            series:
            - Test Series 8:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_backfill_and_begin:
            <<: *nss_backfill
            series:
            - Test Series 9:
                <<: *series_ep_tracking_pack_begin_s02e01
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_from_start:
            <<: *nss_from_start
            series:
            - Test Series 10:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_from_start_backfill:
            <<: *nss_backfill_from_start
            series:
            - Test Series 11:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_from_start_backfill_and_begin:
            <<: *nss_backfill_from_start
            series:
            - Test Series 12:
                <<: *series_ep_tracking_pack_begin_s02e01
            max_reruns: 0
          test_next_series_seasons_season_pack_gap:
            next_series_seasons: yes
            series:
            - Test Series 13:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_gap_backfill:
            <<: *nss_backfill
            series:
            - Test Series 14:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_gap_backfill_and_begin:
            <<: *nss_backfill
            series:
            - Test Series 15:
                <<: *series_ep_tracking_pack_begin_s04e01
            max_reruns: 0
          test_next_series_seasons_season_pack_gap_from_start:
            <<: *nss_from_start
            series:
            - Test Series 16:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_gap_from_start_backfill:
            <<: *nss_backfill_from_start
            series:
            - Test Series 17:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_gap_from_start_backfill_and_begin:
            <<: *nss_backfill_from_start
            series:
            - Test Series 18:
                <<: *series_ep_tracking_pack_begin_s04e01
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_gap:
            next_series_seasons: yes
            series:
            - Test Series 19:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_gap_backfill:
            <<: *nss_backfill
            series:
            - Test Series 20:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_gap_backfill_and_begin:
            <<: *nss_backfill
            series:
            - Test Series 21:
                <<: *series_ep_tracking_pack_begin_s04e01
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_gap_from_start:
            <<: *nss_from_start
            series:
            - Test Series 22:
                <<: *series_ep_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_gap_from_start_backfill:
            <<: *nss_backfill_from_start
            series:
            - Test Series 23:
                <<: *series_ep_tracking_pack
            max_reruns: 0
          test_next_series_seasons_season_pack_and_ep_gap_from_start_backfill_and_begin:
            <<: *nss_backfill_from_start
            series:
            - Test Series 24:
                <<: *series_ep_tracking_pack_begin_s04e01
            max_reruns: 0

          test_next_series_seasons_season_pack_begin_completed:
            next_series_seasons: yes
            series:
            - Test Series 50:
                identified_by: ep
                begin: S02E01
                season_packs:
                  threshold: 1000
                  reject_eps: yes
            max_reruns: 0

          test_next_series_seasons_season_pack_from_start_multirun:
            next_series_seasons:
                from_start: yes
            series:
            - Test Series 100:
                <<: *series_ep_pack
            max_reruns: 0
    """

    @pytest.fixture()
    def config(self):
        """Season packs aren't supported by guessit yet."""
        return self._config

    def inject_series(self, execute_task, release_name):
        execute_task(
            'inject_series',
            options={'inject': [Entry(title=release_name, url='')]},
        )

    @pytest.mark.parametrize(
        "task_name,inject,result_find",
        [
            ('test_next_series_seasons_season_pack', ['Test Series 1 S02'], ['Test Series 1 S03']),
            (
                'test_next_series_seasons_season_pack_backfill',
                ['Test Series 2 S02'],
                ['Test Series 2 S01', 'Test Series 2 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_backfill_and_begin',
                ['Test Series 3 S02'],
                ['Test Series 3 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_from_start',
                ['Test Series 4 S02'],
                ['Test Series 4 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_from_start_backfill',
                ['Test Series 5 S02'],
                ['Test Series 5 S03', 'Test Series 5 S01'],
            ),
            (
                'test_next_series_seasons_season_pack_from_start_backfill_and_begin',
                ['Test Series 6 S02'],
                ['Test Series 6 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep',
                ['Test Series 7 S02', 'Test Series 7 S03E01'],
                ['Test Series 7 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_backfill',
                ['Test Series 8 S02', 'Test Series 8 S03E01'],
                ['Test Series 8 S01', 'Test Series 8 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_backfill_and_begin',
                ['Test Series 9 S02', 'Test Series 9 S03E01'],
                ['Test Series 9 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_from_start',
                ['Test Series 10 S02', 'Test Series 10 S03E01'],
                ['Test Series 10 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_from_start_backfill',
                ['Test Series 11 S02', 'Test Series 11 S03E01'],
                ['Test Series 11 S03', 'Test Series 11 S01'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_from_start_backfill_and_begin',
                ['Test Series 12 S02', 'Test Series 12 S03E01'],
                ['Test Series 12 S03'],
            ),
            (
                'test_next_series_seasons_season_pack_gap',
                ['Test Series 13 S02', 'Test Series 13 S06'],
                ['Test Series 13 S07'],
            ),
            (
                'test_next_series_seasons_season_pack_gap_backfill',
                ['Test Series 14 S02', 'Test Series 14 S06'],
                [
                    'Test Series 14 S07',
                    'Test Series 14 S05',
                    'Test Series 14 S04',
                    'Test Series 14 S03',
                    'Test Series 14 S01',
                ],
            ),
            (
                'test_next_series_seasons_season_pack_gap_backfill_and_begin',
                ['Test Series 15 S02', 'Test Series 15 S06'],
                ['Test Series 15 S07', 'Test Series 15 S05', 'Test Series 15 S04'],
            ),
            (
                'test_next_series_seasons_season_pack_gap_from_start',
                ['Test Series 16 S02', 'Test Series 16 S06'],
                ['Test Series 16 S07'],
            ),
            (
                'test_next_series_seasons_season_pack_gap_from_start_backfill',
                ['Test Series 17 S02', 'Test Series 17 S06'],
                [
                    'Test Series 17 S07',
                    'Test Series 17 S05',
                    'Test Series 17 S04',
                    'Test Series 17 S03',
                    'Test Series 17 S01',
                ],
            ),
            (
                'test_next_series_seasons_season_pack_gap_from_start_backfill_and_begin',
                ['Test Series 18 S02', 'Test Series 18 S06'],
                ['Test Series 18 S07', 'Test Series 18 S05', 'Test Series 18 S04'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_gap',
                ['Test Series 19 S02', 'Test Series 19 S06', 'Test Series 19 S07E01'],
                ['Test Series 19 S07'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_gap_backfill',
                ['Test Series 20 S02', 'Test Series 20 S06', 'Test Series 20 S07E01'],
                [
                    'Test Series 20 S07',
                    'Test Series 20 S05',
                    'Test Series 20 S04',
                    'Test Series 20 S03',
                    'Test Series 20 S01',
                ],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_gap_backfill_and_begin',
                ['Test Series 21 S02', 'Test Series 21 S06', 'Test Series 21 S07E01'],
                ['Test Series 21 S07', 'Test Series 21 S05', 'Test Series 21 S04'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_gap_from_start',
                ['Test Series 22 S02', 'Test Series 22 S03E01', 'Test Series 22 S06'],
                ['Test Series 22 S07'],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_gap_from_start_backfill',
                ['Test Series 23 S02', 'Test Series 23 S03E01', 'Test Series 23 S06'],
                [
                    'Test Series 23 S07',
                    'Test Series 23 S05',
                    'Test Series 23 S04',
                    'Test Series 23 S03',
                    'Test Series 23 S01',
                ],
            ),
            (
                'test_next_series_seasons_season_pack_and_ep_gap_from_start_backfill_and_begin',
                ['Test Series 24 S02', 'Test Series 24 S03E01', 'Test Series 24 S06'],
                ['Test Series 24 S07', 'Test Series 24 S05', 'Test Series 24 S04'],
            ),
            (
                'test_next_series_seasons_season_pack_begin_completed',
                ['Test Series 50 S02'],
                ['Test Series 50 S03'],
            ),
        ],
    )
    def test_next_series_seasons(self, execute_task, task_name, inject, result_find):
        for entity_id in inject:
            self.inject_series(execute_task, entity_id)
        task = execute_task(task_name)
        for result_title in result_find:
            assert task.find_entry(title=result_title)
        assert len(task.all_entries) == len(result_find)

    # Tests which require multiple tasks to be executed in order
    # Each run_parameter is a tuple of lists: [task name, list of series ID(s) to inject, list of result(s) to find]
    @pytest.mark.parametrize(
        "run_parameters",
        [
            (
                [
                    'test_next_series_seasons_season_pack_from_start_multirun',
                    [],
                    ['Test Series 100 S01'],
                ],
                [
                    'test_next_series_seasons_season_pack_from_start_multirun',
                    [],
                    ['Test Series 100 S02'],
                ],
            )
        ],
    )
    def test_next_series_seasons_multirun(self, execute_task, run_parameters):
        for this_test in run_parameters:
            for entity_id in this_test[1]:
                self.inject_series(execute_task, entity_id)
            task = execute_task(this_test[0])
            for result_title in this_test[2]:
                assert task.find_entry(title=result_title)
            assert len(task.all_entries) == len(this_test[2])
