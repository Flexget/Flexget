from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestOnlytask(FlexGetBase):
    """
        Test --task option
    """

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'download', url: 'http://localhost/download'}
          test2:
            mock:
              - {title: 'nodownload', url: 'http://localhost/nodownload'}
    """

    def test_manual_with_onlytask(self):
        # Pretend we have been run with --task test
        self.manager.options.onlytask = 'test'
        # --task plugin uses manager.tasks, so we must create it for this test.
        self.manager.create_tasks()
        # This task should run normally, as we specified it as onlytask
        self.execute_task('test')
        assert self.task.find_entry(title='download'), \
                'task failed to download with --task'
        # This task should be disabled, as it wasn't specified with onlytask
        self.execute_task('test2')
        assert not self.task.find_entry(title='nodownload'), \
                'task should not have been executed'
        # Revert manager settings back to default
        self.manager.options.onlytask = None
        self.manager.tasks = {}


class TestManualAutomatic(FlexGetBase):
    """
        Test manual download tasks
    """

    __yaml__ = """
        tasks:
          test:
            manual: true
            mock:
              - {title: 'nodownload', url: 'http://localhost/nodownload'}
    """

    def test_manual_without_onlytask(self):
        self.execute_task('test')
        assert not self.task.find_entry(title='nodownload'), \
                'Manual tasks downloaded on automatic run'


class TestManualOnlytask(FlexGetBase):
    """
        Test manual download tasks
    """

    __yaml__ = """
        tasks:
          test2:
            manual: true
            mock:
              - {title: 'download', url: 'http://localhost/download'}
    """

    def test_manual_with_onlytask(self):
        # Pretend we have been run with --task test2
        self.manager.options.onlytask = 'test2'
        # --task plugin uses manager.tasks, so we must create it for this test.
        self.manager.create_tasks()
        self.execute_task('test2')
        # Revert manager settings back to default
        self.manager.options.onlytask = None
        self.manager.tasks = {}
        assert self.task.find_entry(title='download'), \
                'Manual tasks failed to download on manual run'
