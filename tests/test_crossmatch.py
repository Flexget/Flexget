from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin


class TestCrossmatch(object):
    config = """
        tasks:
          test_title:
            mock:
            - title: entry 1
            - title: entry 2
            crossmatch:
              from:
              - mock:
                - title: entry 2
              action: reject
              fields: [title]
    """

    def test_reject_title(self, execute_task):
        task = execute_task('test_title')
        assert task.find_entry('rejected', title='entry 2')
        assert len(task.rejected) == 1
