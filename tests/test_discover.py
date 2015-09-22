from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta

from flexget.entry import Entry
from flexget import plugin
from tests import FlexGetBase


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


class TestDiscover(FlexGetBase):
    __yaml__ = """
        tasks:
          test_sort:
            discover:
              ignore_estimations: yes
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
              ignore_estimations: yes
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
              ignore_estimations: yes
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
              ignore_estimations: yes
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

    def test_sort(self):
        self.execute_task('test_sort')
        assert len(self.task.entries) == 3
        # Entries should be ordered by search_sort
        order = list(e.get('search_sort') for e in self.task.entries)
        assert order == sorted(order, reverse=True)

    def test_interval(self):
        self.execute_task('test_interval')
        assert len(self.task.entries) == 1

        # Insert a new entry into the search input
        self.manager.config['tasks']['test_interval']['discover']['what'][0]['mock'].append({'title': 'Bar'})
        self.execute_task('test_interval')
        # First entry should be waiting for interval
        assert len(self.task.entries) == 1
        assert self.task.entries[0]['title'] == 'Bar'

        # Now they should both be waiting
        self.execute_task('test_interval')
        assert len(self.task.entries) == 0

    def test_estimates(self):
        mock_config = self.manager.config['tasks']['test_estimates']['discover']['what'][0]['mock']
        # It should not be searched before the release date
        mock_config[0]['est_release'] = datetime.now() + timedelta(days=7)
        self.execute_task('test_estimates')
        assert len(self.task.entries) == 0
        # It should be searched after the release date
        mock_config[0]['est_release'] = datetime.now()
        self.execute_task('test_estimates')
        assert len(self.task.entries) == 1

    def test_emit_series(self):
        self.execute_task('test_emit_series')
        assert self.task.find_entry(title='My Show S01E01')

    def test_emit_series_with_bad_search(self):
        self.execute_task('test_emit_series_with_bad_search')
        for epnum in xrange(1, 5):
            title = 'My Show S01E0%d' % epnum
            assert any(e['title'] == title for e in self.task.mock_output), '%s not accepted' % title
        assert len(self.task.mock_output) == 4, \
            '4 episodes should have been accepted, not %s' % len(self.task.mock_output)


class TestEmitSeriesInDiscover(FlexGetBase):
    __yaml__ = """
        tasks:
          inject_series:
            series:
              - My Show 2
          test_emit_series_backfill:
            discover:
              ignore_estimations: yes
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

    def inject_series(self, release_name):
        self.execute_task('inject_series', options = {'inject': [Entry(title=release_name, url='')]})

    def test_emit_series_backfill(self):
        self.inject_series('My Show 2 S02E01')
        self.execute_task('test_emit_series_backfill')
        assert self.task.find_entry(title='My Show 2 S01E01')
        assert self.task.find_entry(title='My Show 2 S02E02')
