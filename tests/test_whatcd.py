from __future__ import unicode_literals, division, absolute_import



class TestWhatCDOnline(object):

    config = """
        tasks:
          badlogin:
            whatcd:
              username: invalid
              password: invalid
    """

    def test_invalid_login(self, execute_task, use_vcr):
        task = execute_task("badlogin", abort_ok=True)
        assert task.aborted, 'Task not aborted with invalid login credentials'
