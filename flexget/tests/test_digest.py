class TestDigest:
    config = """
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
          different states:
            mock:
            - title: accepted
            - title: rejected
            regexp:
              accept:
              - accepted
              reject:
              - rejected
            digest:
              list: aoeu
              state: ['accepted', 'rejected']
          emit digest:
            from_digest:
              list: aoeu
            seen: local
          emit state:
            from_digest:
              list: aoeu
              restore_state: yes
            seen: local
          emit limit:
            from_digest:
              list: aoeu
              limit: 3
            seen: local
        """

    def test_multiple_task_merging(self, execute_task):
        execute_task('digest 1')
        execute_task('digest 2')
        task = execute_task('emit digest')
        assert len(task.all_entries) == 2

    def test_same_task_merging(self, execute_task):
        execute_task('digest multi run')
        execute_task('digest multi run')
        task = execute_task('emit digest')
        assert len(task.all_entries) == 2

    def test_expire(self, execute_task):
        execute_task('digest 1')
        task = execute_task('emit digest')
        assert len(task.all_entries) == 1
        task = execute_task('emit digest')
        assert len(task.all_entries) == 0

    def test_limit(self, execute_task):
        execute_task('many entries')
        task = execute_task('emit limit')
        assert len(task.all_entries) == 3

    def test_different_states(self, execute_task):
        execute_task('different states')
        task = execute_task('emit digest')
        assert len(task.all_entries) == 2
        for entry in task.all_entries:
            assert entry.undecided, 'Should have been emitted in undecided state'

    def test_restore_state(self, execute_task):
        execute_task('different states')
        task = execute_task('emit state')
        for entry in task.all_entries:
            assert str(entry.state) == entry['title'], (
                'Should have been emitted in same state as when digested'
            )
