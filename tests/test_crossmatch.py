from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase

class TestCrossmatch(FlexGetBase):
    __yaml__ = """
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

    def test_reject_title(self):
        self.execute_task('test_title')
        assert self.task.find_entry('rejected', title='entry 2')
        assert len(self.task.rejected) == 1
