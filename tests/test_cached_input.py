from __future__ import unicode_literals, division, absolute_import
from datetime import timedelta
import os

from tests import FlexGetBase, with_filecopy
from flexget.utils.cached_input import cached
from flexget import plugin
from flexget.entry import Entry


class InputPersist(object):
    """Fake input plugin to test db cache. Only emits an entry the first time it is run."""

    hasrun = False

    @cached('test_input', persist='5 minutes')
    def on_task_input(self, task, config):
        if self.hasrun:
            return []
        self.hasrun = True
        return [Entry(title='Test', url='http://test.com')]

plugin.register(InputPersist, 'test_input', api_ver=2)


class TestInputCache(FlexGetBase):

    __yaml__ = """
        tasks:
          test_memory:
            rss:
              url: cached.xml
          test_db:
            test_input: True
    """

    @with_filecopy('rss.xml', 'cached.xml')
    def test_memory_cache(self):
        """Test memory input caching"""
        self.execute_task('test_memory')
        assert self.task.entries, 'should have created entries at the start'
        os.remove('cached.xml')
        f = open('cached.xml', 'w')
        f.write('')
        f.close()
        self.execute_task('test_memory')
        assert self.task.entries, 'should have created entries from the cache'
        # Turn the cache time down and run again to make sure the entries are not created again
        from flexget.utils.cached_input import cached
        cached.cache.cache_time = timedelta(minutes=0)
        self.execute_task('test_memory')
        assert not self.task.entries, 'cache should have been expired'

    def test_db_cache(self):
        """Test db input caching"""

        self.execute_task('test_db')
        assert self.task.entries, 'should have created entries at the start'
        self.execute_task('test_db')
        assert self.task.entries, 'should have created entries from the cache'
