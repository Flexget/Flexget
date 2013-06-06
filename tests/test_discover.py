from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta

from flexget.entry import Entry
from flexget.plugin import register_plugin
import flexget.validator
from tests import FlexGetBase


class SearchPlugin(object):
    """Fake search plugin. Just returns the entry it was given."""

    def validator(self):
        return flexget.validator.factory('boolean')

    def search(self, entry, comparator=None, config=None):
        return [Entry(entry)]

register_plugin(SearchPlugin, 'test_search', groups=['search'])


class EstRelease(object):
    """Fake release estimate plugin. Just returns 'est_release' entry field."""

    def estimate(self, entry):
        return entry.get('est_release')

register_plugin(EstRelease, 'test_release', groups=['estimate_release'])


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
