from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase


class TestDigest(FlexGetBase):
    __yaml__ = """
        tasks:
          digest 1:
            mock:
              - title: entry 1
            accept_all: yes
            digest: aoeu
          digest 2:
            mock:
              - title: entry 2
            accept_all: yes
            digest: aoeu
          emit digest:
            seen: local
            emit_digest:
              list: aoeu
        """

    def test_multiple_task_merging(self):
        self.execute_task('digest 1')
        self.execute_task('digest 2')
        self.execute_task('emit digest')
        assert len(self.task.entries) == 2
