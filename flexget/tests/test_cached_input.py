from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from datetime import timedelta

import pytest

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


@pytest.mark.filecopy('rss.xml', '__tmp__/cached.xml')
@pytest.mark.usefixtures('tmpdir')
class TestInputCache(object):
    config = """
        tasks:
          test_memory:
            rss:
              url: __tmp__/cached.xml
          test_db:
            test_input: True
    """

    def test_memory_cache(self, execute_task, tmpdir):
        """Test memory input caching"""
        task = execute_task('test_memory')
        assert task.entries, 'should have created entries at the start'
        tmpdir.join('cached.xml').remove()
        tmpdir.join('cached.xml').write('')
        task = execute_task('test_memory')
        assert task.entries, 'should have created entries from the cache'
        # Turn the cache time down and run again to make sure the entries are not created again
        cached.cache.cache_time = timedelta(minutes=0)
        task = execute_task('test_memory')
        assert not task.entries, 'cache should have been expired'

    def test_db_cache(self, execute_task):
        """Test db input caching"""

        task = execute_task('test_db')
        assert task.entries, 'should have created entries at the start'
        task = execute_task('test_db')
        assert task.entries, 'should have created entries from the cache'
