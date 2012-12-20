from __future__ import unicode_literals, division, absolute_import
import os
from tests import FlexGetBase, with_filecopy
from flexget.utils.cached_input import cached
from flexget.plugin import register_plugin
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

register_plugin(InputPersist, 'test_input', api_ver=2)


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
        # Don't use execute_task in this test as it runs process_start (which clears the cache) before each task
        self.manager.create_tasks()
        self.manager.process_start()
        task = self.manager.tasks['test_memory']
        task.execute()
        assert task.entries, 'should have created entries at the start'
        os.remove('cached.xml')
        f = open('cached.xml', 'w')
        f.write('')
        f.close()
        task = self.manager.tasks['test_memory']
        task.execute()
        assert task.entries, 'should have created entries from the cache'
        self.manager.process_end()

    def test_db_cache(self):
        """Test db input caching"""

        self.execute_task('test_db')
        assert self.task.entries, 'should have created entries at the start'
        self.execute_task('test_db')
        assert self.task.entries, 'should have created entries from the cache'
