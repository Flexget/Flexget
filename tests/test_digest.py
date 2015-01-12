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
          digest multi run:
            mock:
            - title: entry 1
            - title: entry 2
            accept_all: yes
            limit_new: 1
            digest: aoeu
          many entries:
            mock:
            - title: entry 1
            - title: entry 2
            - title: entry 3
            - title: entry 4
            - title: entry 5
            accept_all: yes
            digest: aoeu
          emit digest:
            emit_digest:
              list: aoeu
          emit limit:
            emit_digest:
              list: aoeu
              limit: 3
        """

    def test_multiple_task_merging(self):
        self.execute_task('digest 1')
        self.execute_task('digest 2')
        self.execute_task('emit digest')
        assert len(self.task.all_entries) == 2

    def test_same_task_merging(self):
        self.execute_task('digest multi run')
        self.execute_task('digest multi run')
        self.execute_task('emit digest')
        assert len(self.task.all_entries) == 2

    def test_expire(self):
        self.execute_task('digest 1')
        self.execute_task('emit digest')
        assert len(self.task.all_entries) == 1
        self.execute_task('emit digest')
        assert len(self.task.all_entries) == 0

    def test_limit(self):
        self.execute_task('many entries')
        self.execute_task('emit limit')
        assert len(self.task.all_entries) == 3
