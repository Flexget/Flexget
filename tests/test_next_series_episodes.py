import pytest
from jinja2 import Template

from flexget.entry import Entry


class TestNextSeriesEpisodes:
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
          test_next_series_episodes_backfill:
            next_series_episodes:
              backfill: yes
            series:
            - Test Series 1:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_no_backfill:
            next_series_episodes: yes
            series:
            - Test Series 1
            max_reruns: 0
          test_next_series_episodes_backfill_limit:
            next_series_episodes:
              backfill: yes
              backfill_limit: 10
            series:
            - Test Series 1:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_rejected:
            next_series_episodes:
              backfill: yes
            series:
            - Test Series 2:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_from_start:
            next_series_episodes:
              from_start: yes
            series:
            - Test Series 3:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_begin:
            next_series_episodes: yes
            series:
            - Test Series 4:
                begin: S03E03
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_begin_and_backfill:
            next_series_episodes:
              backfill: yes
            series:
            - Test Series 5:
                begin: S03E02
            max_reruns: 0
          test_next_series_episodes_begin_backfill_and_rerun:
            accept_all: yes  # make sure mock output stores all created entries
            next_series_episodes:
              backfill: yes
            series:
            - Test Series 6:
                begin: S03E02
            mock_output: yes
            max_reruns: 1
          test_next_series_episodes_backfill_advancement:
            next_series_episodes:
              backfill: yes
            series:
            - Test Series 7:
                identified_by: ep
            regexp:
              reject:
              - .
          test_next_series_episodes_advancement:
            next_series_episodes: yes
            series:
            - Test Series 8:
                identified_by: ep
            regexp:
              reject:
              - .
          test_next_series_episodes_alternate_name:
            next_series_episodes: yes
            series:
            - Test Series 8:
               begin: S01E01
               alternate_name:
                 - Testing Series 8
                 - Tests Series 8
            max_reruns: 0
            mock_output: yes
          test_next_series_episodes_alternate_name_duplicates:
            next_series_episodes: yes
            series:
            - Test Series 8:
               begin: S01E01
               alternate_name:
                 - Testing Series 8
                 - Testing SerieS 8
            max_reruns: 0
            mock_output: yes
          test_next_series_episodes_only_same_season:
            next_series_episodes:
              only_same_season: yes
            series:
            - Test Series 8:
                identified_by: ep
            regexp:
              reject:
              - .
    """

    @pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request):
        """Override and parametrize default config fixture."""
        return Template(self._config).render({'parser': request.param})

    def inject_series(self, execute_task, release_name):
        execute_task(
            'inject_series',
            options={'inject': [Entry(title=release_name, url='')]},
        )

    def test_next_series_episodes_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 1 S02E01')
        task = execute_task('test_next_series_episodes_backfill')
        assert task.find_entry(title='Test Series 1 S01E01')
        assert task.find_entry(title='Test Series 1 S02E02')
        task = execute_task('test_next_series_episodes_backfill')
        assert task.find_entry(title='Test Series 1 S01E02')
        assert task.find_entry(title='Test Series 1 S02E03')
        self.inject_series(execute_task, 'Test Series 1 S02E08')
        task = execute_task('test_next_series_episodes_backfill')
        assert task.find_entry(title='Test Series 1 S01E03')
        assert task.find_entry(title='Test Series 1 S02E04')
        assert task.find_entry(title='Test Series 1 S02E05')
        assert task.find_entry(title='Test Series 1 S02E06')
        assert task.find_entry(title='Test Series 1 S02E07')

    def test_next_series_episodes_no_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 1 S01E01')
        self.inject_series(execute_task, 'Test Series 1 S01E05')
        task = execute_task('test_next_series_episodes_no_backfill')
        assert len(task.all_entries) == 1
        assert task.find_entry(title='Test Series 1 S01E06')

    def test_next_series_episodes_backfill_limit(self, execute_task):
        self.inject_series(execute_task, 'Test Series 1 S01E01')
        self.inject_series(execute_task, 'Test Series 1 S01E13')
        task = execute_task('test_next_series_episodes_backfill_limit')
        assert len(task.all_entries) == 1, "missing episodes over limit. Should not backfill"
        self.inject_series(execute_task, 'Test Series 1 S01E12')
        task = execute_task('test_next_series_episodes_backfill_limit')
        assert len(task.all_entries) == 11, "missing episodes less than limit. Should backfill"

    def test_next_series_episodes_rejected(self, execute_task):
        self.inject_series(execute_task, 'Test Series 2 S01E03 720p')
        task = execute_task('test_next_series_episodes_rejected')
        assert task.find_entry(title='Test Series 2 S01E01')
        assert task.find_entry(title='Test Series 2 S01E02')
        assert task.find_entry(title='Test Series 2 S01E03')

    def test_next_series_episodes_from_start(self, execute_task):
        task = execute_task('test_next_series_episodes_from_start')
        assert task.find_entry(title='Test Series 3 S01E01')
        task = execute_task('test_next_series_episodes_from_start')
        assert task.find_entry(title='Test Series 3 S01E02')

    def test_next_series_episodes_begin(self, execute_task):
        task = execute_task('test_next_series_episodes_begin')
        assert task.find_entry(title='Test Series 4 S03E03')

    def test_next_series_episodes_begin_and_backfill(self, execute_task):
        self.inject_series(execute_task, 'Test Series 5 S02E02')
        task = execute_task('test_next_series_episodes_begin_and_backfill')
        # with backfill and begin, no backfilling should be done
        assert task.find_entry(title='Test Series 5 S03E02')
        assert len(task.all_entries) == 1

    def test_next_series_episodes_begin_backfill_and_rerun(self, execute_task):
        self.inject_series(execute_task, 'Test Series 6 S03E01')
        task = execute_task('test_next_series_episodes_begin_backfill_and_rerun')
        # with backfill and begin, no backfilling should be done
        assert task._rerun_count == 1
        assert task.find_entry(title='Test Series 6 S03E03')
        assert len(task.all_entries) == 1
        assert len(task.mock_output) == 2  # Should have S03E02 and S03E03

    def test_next_series_episodes_backfill_advancement(self, execute_task):
        self.inject_series(execute_task, 'Test Series 7 S02E01')
        task = execute_task('test_next_series_episodes_backfill_advancement')
        assert task._rerun_count == 1
        assert len(task.all_entries) == 1
        assert task.find_entry('rejected', title='Test Series 7 S03E01')

    def test_next_series_episodes_advancement(self, execute_task):
        self.inject_series(execute_task, 'Test Series 8 S01E01')
        task = execute_task('test_next_series_episodes_advancement')
        assert task._rerun_count == 1
        assert len(task.all_entries) == 1
        assert task.find_entry('rejected', title='Test Series 8 S02E01')

    def test_next_series_episodes_alternate_name(self, execute_task):
        task = execute_task('test_next_series_episodes_alternate_name')
        assert len(task.mock_output) == 1
        # There should be 2 alternate names
        assert len(task.mock_output[0].get('series_alternate_names')) == 2
        expected = task.mock_output[0].get('series_alternate_names').sort()
        actual = ['Testing Series 8', 'Tests Series 8'].sort()
        assert expected == actual, 'Alternate names do not match (how?).'

    def test_next_series_episodes_alternate_name_duplicates(self, execute_task):
        task = execute_task('test_next_series_episodes_alternate_name_duplicates')
        assert len(task.mock_output) == 1
        # duplicate alternate names should only result in 1
        # even if it is not a 'complete match' (eg. My Show == My SHOW)
        assert len(task.mock_output[0].get('series_alternate_names')) == 1, (
            'Duplicate alternate names.'
        )

    def test_next_series_episodes_search_strings(self, execute_task):
        # This test makes sure that the number of search strings increases when the amount of alt names increases.
        task = execute_task('test_next_series_episodes_alternate_name_duplicates')
        s1 = len(task.mock_output[0].get('search_strings'))
        task = execute_task('test_next_series_episodes_alternate_name')
        s2 = len(task.mock_output[0].get('search_strings'))
        assert s2 > s1, 'Alternate names did not create sufficient search strings.'

    def test_next_series_episodes_only_same_season(self, execute_task):
        self.inject_series(execute_task, 'Test Series 8 S01E01')
        task = execute_task('test_next_series_episodes_only_same_season')
        assert task._rerun_count == 0
        assert len(task.all_entries) == 1
        assert not task.find_entry(title='Test Series 8 S02E01')


class TestNextSeriesEpisodesSeasonPack:
    _config = """
        templates:
          global:
            parsing:
              series: internal
          anchors:
            _nse_backfill: &nse_backfill
              next_series_episodes:
                backfill: yes
            _nse_from_start: &nse_from_start
              next_series_episodes:
                from_start: yes
            _nse_backfill_from_start: &nse_backfill_from_start
              next_series_episodes:
                backfill: yes
                from_start: yes
            _series_ep_tracking_begin_s04e01: &series_ep_tracking_begin_s04e01
              identified_by: ep
              begin: s04e01
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
          test_next_series_episodes_season_pack:
            next_series_episodes: yes
            series:
            - Test Series 1:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_backfill:
            <<: *nse_backfill
            series:
            - Test Series 2:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_from_start:
            <<: *nse_from_start
            series:
            - Test Series 4:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_from_start_backfill:
            <<: *nse_backfill_from_start
            series:
            - Test Series 5:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep:
            next_series_episodes: yes
            series:
            - Test Series 7:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_backfill:
            <<: *nse_backfill
            series:
            - Test Series 8:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_backfill_and_begin:
            <<: *nse_backfill
            series:
            - Test Series 9:
                identified_by: ep
                begin: s02e01
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_from_start:
            <<: *nse_from_start
            series:
            - Test Series 10:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_from_start_backfill:
            <<: *nse_backfill_from_start
            series:
            - Test Series 11:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_from_start_backfill_and_begin:
            <<: *nse_backfill_from_start
            series:
            - Test Series 12:
                  identified_by: ep
                  begin: s02e01
            max_reruns: 0
          test_next_series_episodes_season_pack_gap:
            next_series_episodes: yes
            series:
            - Test Series 13:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_gap_backfill:
            <<: *nse_backfill
            series:
            - Test Series 14:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_gap_backfill_and_begin:
            <<: *nse_backfill
            series:
            - Test Series 15:
                identified_by: ep
                begin: s04e01
            max_reruns: 0
          test_next_series_episodes_season_pack_gap_from_start:
            <<: *nse_from_start
            series:
            - Test Series 16:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_gap_from_start_backfill:
            <<: *nse_backfill_from_start
            series:
            - Test Series 17:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_gap_from_start_backfill_and_begin:
            <<: *nse_backfill_from_start
            series:
            - Test Series 18:
                identified_by: ep
                begin: s04e01
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_gap:
            next_series_episodes: yes
            series:
            - Test Series 19:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_gap_backfill:
            <<: *nse_backfill
            series:
            - Test Series 20:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_gap_backfill_and_begin:
            <<: *nse_backfill
            series:
            - Test Series 21:
                identified_by: ep
                begin: s04e01
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_gap_from_start:
            <<: *nse_from_start
            series:
            - Test Series 22:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_gap_from_start_backfill:
            <<: *nse_backfill_from_start
            series:
            - Test Series 23:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_season_pack_and_ep_gap_from_start_backfill_and_begin:
            <<: *nse_backfill_from_start
            series:
            - Test Series 24:
                identified_by: ep
                begin: s04e01
            max_reruns: 0

          test_next_series_episodes_season_pack_begin_completed:
            next_series_episodes: yes
            series:
            - Test Series 50:
                identified_by: ep
                begin: S02E01
            max_reruns: 0

          test_next_series_episodes_season_pack_from_start_multirun:
            next_series_episodes:
                from_start: yes
            series:
            - Test Series 100:
                identified_by: ep
            max_reruns: 0
    """

    @pytest.fixture
    def config(self):
        """Season packs aren't supported by guessit yet."""
        return self._config

    def inject_series(self, execute_task, release_name):
        execute_task(
            'inject_series',
            options={'inject': [Entry(title=release_name, url='')]},
        )

    @pytest.mark.parametrize(
        ('task_name', 'inject', 'result_find'),
        [
            (
                'test_next_series_episodes_season_pack',
                ['Test Series 1 S02'],
                ['Test Series 1 S03E01'],
            ),
            (
                'test_next_series_episodes_season_pack_backfill',
                ['Test Series 2 S02'],
                ['Test Series 2 S01E01', 'Test Series 2 S03E01'],
            ),
            (
                'test_next_series_episodes_season_pack_from_start',
                ['Test Series 4 S02'],
                ['Test Series 4 S03E01'],
            ),
            (
                'test_next_series_episodes_season_pack_from_start_backfill',
                ['Test Series 5 S02'],
                ['Test Series 5 S03E01', 'Test Series 5 S01E01'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep',
                ['Test Series 7 S02', 'Test Series 7 S03E01'],
                ['Test Series 7 S03E02'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_backfill',
                ['Test Series 8 S02', 'Test Series 8 S03E01'],
                ['Test Series 8 S01E01', 'Test Series 8 S03E02'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_backfill_and_begin',
                ['Test Series 9 S02', 'Test Series 9 S03E01'],
                ['Test Series 9 S03E02'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_from_start',
                ['Test Series 10 S02', 'Test Series 10 S03E01'],
                ['Test Series 10 S03E02'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_from_start_backfill',
                ['Test Series 11 S02', 'Test Series 11 S03E01'],
                ['Test Series 11 S03E02', 'Test Series 11 S01E01'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_from_start_backfill_and_begin',
                ['Test Series 12 S02', 'Test Series 12 S03E01'],
                ['Test Series 12 S03E02'],
            ),
            (
                'test_next_series_episodes_season_pack_gap',
                ['Test Series 13 S02', 'Test Series 13 S06'],
                ['Test Series 13 S07E01'],
            ),
            (
                'test_next_series_episodes_season_pack_gap_backfill',
                ['Test Series 14 S02', 'Test Series 14 S06'],
                [
                    'Test Series 14 S07E01',
                    'Test Series 14 S05E01',
                    'Test Series 14 S04E01',
                    'Test Series 14 S03E01',
                    'Test Series 14 S01E01',
                ],
            ),
            (
                'test_next_series_episodes_season_pack_gap_backfill_and_begin',
                ['Test Series 15 S02', 'Test Series 15 S06'],
                ['Test Series 15 S07E01', 'Test Series 15 S05E01', 'Test Series 15 S04E01'],
            ),
            (
                'test_next_series_episodes_season_pack_gap_from_start',
                ['Test Series 16 S02', 'Test Series 16 S06'],
                ['Test Series 16 S07E01'],
            ),
            (
                'test_next_series_episodes_season_pack_gap_from_start_backfill',
                ['Test Series 17 S02', 'Test Series 17 S06'],
                [
                    'Test Series 17 S07E01',
                    'Test Series 17 S05E01',
                    'Test Series 17 S04E01',
                    'Test Series 17 S03E01',
                    'Test Series 17 S01E01',
                ],
            ),
            (
                'test_next_series_episodes_season_pack_gap_from_start_backfill_and_begin',
                ['Test Series 18 S02', 'Test Series 18 S06'],
                ['Test Series 18 S07E01', 'Test Series 18 S05E01', 'Test Series 18 S04E01'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_gap',
                ['Test Series 19 S02', 'Test Series 19 S06', 'Test Series 19 S07E01'],
                ['Test Series 19 S07E02'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_gap_backfill',
                ['Test Series 20 S02', 'Test Series 20 S06', 'Test Series 20 S07E01'],
                [
                    'Test Series 20 S07E02',
                    'Test Series 20 S05E01',
                    'Test Series 20 S04E01',
                    'Test Series 20 S03E01',
                    'Test Series 20 S01E01',
                ],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_gap_backfill_and_begin',
                ['Test Series 21 S02', 'Test Series 21 S06', 'Test Series 21 S07E01'],
                ['Test Series 21 S07E02', 'Test Series 21 S05E01', 'Test Series 21 S04E01'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_gap_from_start',
                ['Test Series 22 S02', 'Test Series 22 S03E01', 'Test Series 22 S06'],
                ['Test Series 22 S07E01'],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_gap_from_start_backfill',
                ['Test Series 23 S02', 'Test Series 23 S03E01', 'Test Series 23 S06'],
                [
                    'Test Series 23 S07E01',
                    'Test Series 23 S05E01',
                    'Test Series 23 S04E01',
                    'Test Series 23 S03E02',
                    'Test Series 23 S01E01',
                ],
            ),
            (
                'test_next_series_episodes_season_pack_and_ep_gap_from_start_backfill_and_begin',
                ['Test Series 24 S02', 'Test Series 24 S03E01', 'Test Series 24 S06'],
                ['Test Series 24 S07E01', 'Test Series 24 S05E01', 'Test Series 24 S04E01'],
            ),
            (
                'test_next_series_episodes_season_pack_begin_completed',
                ['Test Series 50 S02'],
                ['Test Series 50 S03E01'],
            ),
        ],
    )
    def test_next_series_episodes_season_pack(self, execute_task, task_name, inject, result_find):
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
                    'test_next_series_episodes_season_pack_from_start_multirun',
                    [],
                    ['Test Series 100 S01E01'],
                ],
                [
                    'test_next_series_episodes_season_pack_from_start_multirun',
                    [],
                    ['Test Series 100 S01E02'],
                ],
            )
        ],
    )
    def test_next_series_episodes_season_pack_multirun(self, execute_task, run_parameters):
        for this_test in run_parameters:
            for entity_id in this_test[1]:
                self.inject_series(execute_task, entity_id)
            task = execute_task(this_test[0])
            for result_title in this_test[2]:
                assert task.find_entry(title=result_title)
            assert len(task.all_entries) == len(this_test[2])
