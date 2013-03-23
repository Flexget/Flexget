from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestBacklog(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'Test.S01E01.hdtv-FlexGet', description: ''}
            set:
              description: '%(description)sI'
              laterfield: 'something'
            # Change the priority of set plugin so it runs on all entries. TODO: Remove, this is an ugly hack.
            plugin_priority:
              set: -254
            backlog: 10 minutes
    """

    def test_backlog(self):
        """Tests backlog (and snapshot) functionality."""

        # Test entry comes out as expected on first run
        self.execute_task('test')
        entry = self.task.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == 'I'
        assert entry['laterfield'] == 'something'
        # Simulate entry leaving the task, make sure backlog injects it
        del(self.task.config['mock'])
        self.execute_task('test')
        entry = self.task.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == 'I'
        assert entry['laterfield'] == 'something'
        # This time take away the set plugin too, to make sure data is being restored at it's state from input
        del(self.task.config['set'])
        self.execute_task('test')
        entry = self.task.find_entry(title='Test.S01E01.hdtv-FlexGet')
        assert entry['description'] == ''
        assert 'laterfield' not in entry
