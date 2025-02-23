from datetime import timedelta

import pytest

from flexget import plugin
from flexget.entry import Entry
from flexget.utils.cached_input import cached


class InputPersist:
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
class TestInputCache:
    config = """
        tasks:
          test_memory:
            rss:
              url: __tmp__/cached.xml
          test_db:
            test_input: True
    """

    def test_memory_cache(self, execute_task, tmp_path):
        """Test memory input caching."""
        task = execute_task('test_memory')
        assert task.entries, 'should have created entries at the start'
        tmp_path.joinpath('cached.xml').unlink()
        tmp_path.joinpath('cached.xml').write_text('')
        task = execute_task('test_memory')
        assert task.entries, 'should have created entries from the cache'
        # Turn the cache time down and run again to make sure the entries are not created again
        cached.cache.cache_time = timedelta(minutes=0)
        task = execute_task('test_memory')
        assert not task.entries, 'cache should have been expired'

    def test_db_cache(self, execute_task):
        """Test db input caching."""
        task = execute_task('test_db')
        assert task.entries, 'should have created entries at the start'
        # Clear out the memory cache to make sure we are loading from db
        cached.cache.clear()
        task = execute_task('test_db')
        assert task.entries, 'should have created entries from the cache'
