from datetime import datetime, timedelta

from flexget import plugin
from flexget.entry import Entry


class SearchPlugin:
    """
    Fake search plugin. Result differs depending on config value:
      `'fail'`: raises a PluginError
      `False`: Returns an empty list
      list of suffixes:
        Returns a list of entries with the same title searched for, but with each of the suffixes appended
      otherwise: Just passes back the entry that was searched for
    """

    schema = {}

    def search(self, task, entry, config=None):
        if not config:
            return []
        if config == 'fail':
            raise plugin.PluginError('search plugin failure')
        if isinstance(config, list):
            return [Entry({**entry, 'title': entry['title'] + suffix}) for suffix in config]
        return [Entry(entry)]


plugin.register(SearchPlugin, 'test_search', interfaces=['search'], api_ver=2)


class EstRelease:
    """Fake release estimate plugin. Just returns 'est_release' entry field."""

    def estimate(self, entry):
        return entry.get('est_release')


plugin.register(EstRelease, 'test_release', interfaces=['estimate_release'], api_ver=2)


class TestDiscover:
    config = """
        tasks:
          test_interval:
            discover:
              release_estimations: ignore
              what:
              - mock:
                - title: Foo
              from:
              - test_search: yes
          test_estimates:
            discover:
              interval: 0 seconds
              what:
              - mock:
                - title: Foo
              from:
              - test_search: yes
          test_next_series_episodes:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes:
                  from_start: yes
              from:
              - test_search: yes
            series:
            - My Show:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_with_bad_search:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes:
                  from_start: yes
              from:
              - test_search: fail
              - test_search: no
              - test_search: yes
            series:
            - My Show:
                identified_by: ep
            mock_output: yes
            max_reruns: 3
          test_next_series_episodes_with_multiple_results:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes:
                  from_start: yes
              from:
              - test_search: [' a', ' b', ' c']
            series:
            - My Show:
                identified_by: ep
            mock_output: yes
            max_reruns: 3

    """

    def test_interval(self, execute_task, manager):
        task = execute_task('test_interval')
        assert len(task.entries) == 1

        # Insert a new entry into the search input
        manager.config['tasks']['test_interval']['discover']['what'][0]['mock'].append(
            {'title': 'Bar'}
        )
        task = execute_task('test_interval')
        # First entry should be waiting for interval
        assert len(task.entries) == 1
        assert task.entries[0]['title'] == 'Bar'

        # Now they should both be waiting
        task = execute_task('test_interval')
        assert len(task.entries) == 0

    def test_estimates(self, execute_task, manager):
        mock_config = manager.config['tasks']['test_estimates']['discover']['what'][0]['mock']
        # It should not be searched before the release date
        mock_config[0]['est_release'] = {
            'data_exists': True,
            'entity_date': (datetime.now() + timedelta(days=7)),
        }
        task = execute_task('test_estimates')
        assert len(task.entries) == 0
        # It should be searched after the release date
        mock_config[0]['est_release'] = {'data_exists': True, 'entity_date': datetime.now()}
        task = execute_task('test_estimates')
        assert len(task.entries) == 1

    def test_next_series_episodes(self, execute_task):
        task = execute_task('test_next_series_episodes')
        assert task.find_entry(title='My Show S01E01')

    def test_next_series_episodes_with_bad_search(self, execute_task):
        task = execute_task('test_next_series_episodes_with_bad_search')
        for epnum in range(1, 5):
            title = f'My Show S01E0{epnum}'
            assert any(e['title'] == title for e in task.mock_output), f'{title} not accepted'
        assert len(task.mock_output) == 4, (
            f'4 episodes should have been accepted, not {len(task.mock_output)}'
        )

    def test_next_series_episodes_multiple_results(self, execute_task):
        # Makes sure the next episode is being searched for on reruns, even when there are multiple search
        # results per episode.
        task = execute_task('test_next_series_episodes_with_multiple_results')
        assert len(task.mock_output) == 4, 'Should have kept rerunning and accepted 4 episodes'
        assert task.find_entry(title='My Show S01E04 a')


class TestEmitSeriesInDiscover:
    config = """
        tasks:
          inject_series:
            series:
              - My Show 1:
                  quality: 720p
                  season_packs: yes
              - My Show 2:
                  season_packs: yes
          test_next_series_episodes_backfill:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes:
                  backfill: yes
              from:
              - test_search: yes
            series:
            - My Show 2:
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes: yes
              from:
              - test_search: yes
            series:
            - My Show 2:
                begin: s02e01
                identified_by: ep
            max_reruns: 0
          test_next_series_episodes_rerun:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes: yes
              from:
              - test_search: yes
            series:
            - My Show 2:
                begin: s02e01
                identified_by: ep
            max_reruns: 3
          test_next_series_episodes_with_unaccepted_season:
            discover:
              release_estimations: ignore
              what:
              - next_series_episodes: yes
              from:
              - test_search: yes
            series:
            - My Show 1:
                begin: s02e01
                identified_by: ep
            max_reruns: 0
          test_next_series_seasons:
            discover:
              release_estimations: ignore
              what:
              - next_series_seasons: yes
              from:
              - test_search: yes
            series:
            - My Show 2:
                begin: s02e01
                identified_by: ep
                season_packs: yes
            max_reruns: 0
    """

    def test_next_series_episodes_rerun(self, execute_task):
        task = execute_task('test_next_series_episodes_rerun')
        # It should rerun 3 times, and on the last time accept episode 4
        assert task.find_entry(category='accepted', title='My Show 2 S02E04')

    def test_next_series_episodes_backfill(self, execute_task):
        execute_task(
            'inject_series', options={'inject': [Entry(title='My Show 2 S02E01', url='')]}
        )
        task = execute_task('test_next_series_episodes_backfill')
        assert task.find_entry(title='My Show 2 S01E01')
        assert task.find_entry(title='My Show 2 S02E02')

    def test_next_series_episodes_backfill_with_completed_season(self, execute_task):
        execute_task('inject_series', options={'inject': [Entry(title='My Show 2 S02', url='')]})
        task = execute_task('test_next_series_episodes_backfill')
        assert task.find_entry(title='My Show 2 S01E01')

    def test_next_series_episodes_with_completed_season(self, execute_task):
        execute_task(
            'inject_series',
            options={
                'inject': [
                    Entry(title='My Show 2 S02', url=''),
                    Entry(title='My Show 2 S01', url=''),
                ]
            },
        )
        task = execute_task('test_next_series_episodes')
        assert task.find_entry(title='My Show 2 S03E01')

    def test_next_series_episodes_with_uncompleted_season(self, execute_task):
        execute_task(
            'inject_series', options={'inject': [Entry(title='My Show 1 S02 480p', url='')]}
        )
        task = execute_task('test_next_series_episodes_with_unaccepted_season')
        assert task.find_entry(title='My Show 1 S02E01')

    def test_next_series_seasons(self, execute_task):
        task = execute_task('test_next_series_seasons')
        assert task.find_entry(title='My Show 2 S02')

    def test_next_series_seasons_with_completed_seasons(self, execute_task):
        execute_task(
            'inject_series',
            options={
                'inject': [
                    Entry(title='My Show 2 S02', url=''),
                    Entry(title='My Show 2 S01', url=''),
                ]
            },
        )
        task = execute_task('test_next_series_seasons')
        assert task.find_entry(title='My Show 2 S03')
