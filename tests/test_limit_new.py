from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestLimitNew(FlexGetBase):
    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'Item 1'}
              - {title: 'Item 2'}
              - {title: 'Item 3'}
              - {title: 'Item 4'}
            accept_all: yes
            limit_new: 1
    """

    def test_limit_new(self):
        self.execute_task('test')
        assert len(self.task.entries) == 1, 'accepted too many'
        assert self.task.find_entry('accepted', title='Item 1'), 'accepted wrong item'
        self.execute_task('test')
        assert len(self.task.entries) == 1, 'accepted too many on second run'
        assert self.task.find_entry('accepted', title='Item 2'), 'accepted wrong item on second run'
