from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase, use_vcr


class TestWhatCDOnline(object):

    config = """
        tasks:
          badlogin:
            whatcd:
              username: invalid
              password: invalid
    """

    @use_vcr
    def test_invalid_login(self, execute_task):
        task = execute_task("badlogin", abort_ok=True)
        assert task.aborted, 'Task not aborted with invalid login credentials'
