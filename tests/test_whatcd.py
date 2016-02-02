from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, use_vcr


class TestWhatCDOnline(FlexGetBase):

    __yaml__ = """
        tasks:
          badlogin:
            whatcd:
              username: invalid
              password: invalid
    """

    @use_vcr
    def test_invalid_login(self):
        self.execute_task("badlogin", abort_ok=True)
        assert self.task.aborted, 'Task not aborted with invalid login credentials'
