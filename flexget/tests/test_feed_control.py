import pytest


class TestOnlyTask:
    """Test --task option."""

    config = """
        tasks:
          test:
            mock:
              - {title: 'download', url: 'http://localhost/download'}
          test2:
            mock:
              - {title: 'nodownload', url: 'http://localhost/nodownload'}
    """

    @pytest.mark.skip(reason="1.2 we need to test this with execute command")
    def test_manual_with_onlytask(self, execute_task):
        # TODO: 1.2 we need to test this with execute command
        # Pretend we have been run with --task test
        # This task should run normally, as we specified it as onlytask
        task = execute_task('test', options={"tasks": ['test']})
        assert task.find_entry(title='download'), 'task failed to download with --task'
        # This task should be disabled, as it wasn't specified with onlytask
        task = execute_task('test2', options={"tasks": ['test']}, abort_ok=True)
        assert task.aborted
        assert not task.find_entry(title='nodownload'), 'task should not have been executed'


class TestManualAutomatic:
    """Test manual download tasks."""

    config = """
        tasks:
          test:
            manual: true
            mock:
              - {title: 'nodownload', url: 'http://localhost/nodownload'}
    """

    def test_manual_without_onlytask(self, execute_task):
        task = execute_task('test', abort=True)
        assert task.aborted
        assert not task.find_entry(title='nodownload'), 'Manual tasks downloaded on automatic run'

    def test_manual_with_startasks(self, execute_task):
        """Specify just '*' as the tasks option should be considered the same as not specifying any specific tasks."""
        task = execute_task('test', abort=True, options={'tasks': ['*'], 'allow_manual': True})
        assert task.aborted
        assert not task.find_entry(title='nodownload'), 'Manual tasks downloaded on automatic run'


class TestManualOnlytask:
    """Test manual download tasks."""

    config = """
        tasks:
          test2:
            manual: true
            mock:
              - {title: 'download', url: 'http://localhost/download'}
    """

    def test_manual_with_onlytask(self, execute_task):
        # Pretend we have been run with --task test2
        task = execute_task('test2', options={"tasks": ['test2'], "allow_manual": True})
        assert task.find_entry(title='download'), 'Manual tasks failed to download on manual run'
