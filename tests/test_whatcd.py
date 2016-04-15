from __future__ import unicode_literals, division, absolute_import

import pytest


@pytest.mark.online
class TestWhatCDOnline(object):

    config = """
        tasks:
          badlogin:
            whatcd:
              username: invalid
              password: invalid
    """

    def test_invalid_login(self, execute_task):
        task = execute_task("badlogin", abort=True)
        assert task.aborted, 'Task not aborted with invalid login credentials'
