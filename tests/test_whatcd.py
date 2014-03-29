from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestInputWhatCD(FlexGetBase):

    __yaml__ = """
        tasks:
          no_fields:
            whatcd:
          no_user:
            whatcd:
              password: test
          no_pass:
            whatcd:
              username: test
    """

    def test_missing_fields(self):
        self.execute_task('no_fields', abort_ok=True)
        assert self.task.aborted, 'Task not aborted with no fields present'
        self.execute_task('no_user', abort_ok=True)
        assert self.task.aborted, 'Task not aborted with no username'
        self.execute_task('no_pass', abort_ok=True)
        assert self.task.aborted, 'Task not aborted with no password'


class TestWhatCDOnline(FlexGetBase):

    __yaml__ = """
        tasks:
          badlogin:
            whatcd:
              username: invalid
              password: invalid
    """

    @attr(online=True)
    def test_invalid_login(self):
        self.execute_task("badlogin", abort_ok=True)
        assert self.task.aborted, 'Task not aborted with invalid login credentials'
