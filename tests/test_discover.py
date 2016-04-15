from __future__ import unicode_literals, division, absolute_import
from builtins import *

from datetime import datetime, timedelta

from flexget.entry import Entry
from flexget import plugin


class SearchPlugin(object):
    """
    Fake search plugin. Result differs depending on config value:
      `'fail'`: raises a PluginError
      `False`: Returns an empty list
      otherwise: Just passes back the entry that was searched for
    """

    schema = {}

    def search(self, task, entry, config=None):
        if not config:
            return []
        elif config == 'fail':
            raise plugin.PluginError('search plugin failure')
        return [Entry(entry)]

plugin.register(SearchPlugin, 'test_search', groups=['search'], api_ver=2)


class EstRelease(object):
    """Fake release estimate plugin. Just returns 'est_release' entry field."""

    def estimate(self, entry):
        return entry.get('est_release')

plugin.register(EstRelease, 'test_release', groups=['estimate_release'], api_ver=2)


class TestDiscover(object):
    config = """
        tasks:
          test_sort:
            discover:
              release_estimations: ignore
              what:
              - mock:
                - title: Foo
                  search_sort: 1
                - title: Bar
                  search_sort: 3
                - title: Baz
                  search_sort: 2
              from:
              - test_search: yes
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
          test_emit_series:
            discover:
              release_estimations: ignore
              what:
              - emit_series:
                  from_start: yes
              from:
              - test_search: yes
            series:
            - My Show:
                identified_by: ep
            rerun: 0
          test_emit_series_with_bad_search:
            discover:
              release_estimations: ignore
              what:
              - emit_series:
                  from_start: yes
              from:
              - test_search: fail
              - test_search: no
              - test_search: yes
            series:
            - My Show:
                identified_by: ep
            mock_output: yes
            rerun: 3

    """

    def test_sort(self, execute_task):
        task = execute_task('test_sort')
        assert len(task.entries) == 3
        # Entries should be ordered by search_sort
        order = list(e.get('search_sort') for e in task.entries)
        assert order == sorted(order, reverse=True)

    def test_interval(self, execute_task, manager):
        task = execute_task('test_interval')
        assert len(task.entries) == 1

        # Insert a new entry into the search input
        manager.config['tasks']['test_interval']['discover']['what'][0]['mock'].append({'title': 'Bar'})
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
        mock_config[0]['est_release'] = datetime.now() + timedelta(days=7)
        task = execute_task('test_estimates')
        assert len(task.entries) == 0
        # It should be searched after the release date
        mock_config[0]['est_release'] = datetime.now()
        task = execute_task('test_estimates')
        assert len(task.entries) == 1

    def test_emit_series(self, execute_task):
        task = execute_task('test_emit_series')
        assert task.find_entry(title='My Show S01E01')

    def test_emit_series_with_bad_search(self, execute_task):
        task = execute_task('test_emit_series_with_bad_search')
        for epnum in range(1, 5):
            title = 'My Show S01E0%d' % epnum
            assert any(e['title'] == title for e in task.mock_output), '%s not accepted' % title
        assert len(task.mock_output) == 4, \
            '4 episodes should have been accepted, not %s' % len(task.mock_output)


class TestEmitSeriesInDiscover(object):
    config = """
        tasks:
          inject_series:
            series:
              - My Show 2
          test_emit_series_backfill:
            discover:
              release_estimations: ignore
              what:
              - emit_series:
                  backfill: yes
              from:
              - test_search: yes
            series:
            - My Show 2:
                tracking: backfill
                identified_by: ep
            rerun: 0
    """

    def test_emit_series_backfill(self, execute_task):
        execute_task('inject_series', options = {'inject': [Entry(title='My Show 2 S02E01', url='')]})
        task = execute_task('test_emit_series_backfill')
        assert task.find_entry(title='My Show 2 S01E01')
        assert task.find_entry(title='My Show 2 S02E02')
