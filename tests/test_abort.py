from tests import FlexGetBase


class TestAbort(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            # causes on_task_abort to be called
            disable_builtins: yes

            # causes abort
            nzb_size: 10

            # another event hookup with this plugin
            headers:
              test: value
    """

    def test_abort(self):
        self.execute_task('test')
        assert self.task._abort, 'Task not aborted'
