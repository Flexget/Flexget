class TestDuplicates:
    config = """
        tasks:
          duplicates_accept:
            mock:
              - {title: 'entry 1', url: 'http://foo.bar', another_field: 'bla'}
              - {title: 'entry 2', url: 'http://foo.baz', another_field: 'bla'}
            duplicates:
              field: another_field
              action: accept
          duplicates_reject:
            mock:
              - {title: 'entry 1', url: 'http://foo.bar', another_field: 'bla'}
              - {title: 'entry 2', url: 'http://foo.baz', another_field: 'bla'}
            duplicates:
              field: another_field
              action: reject
          duplicates_missing_field:
            mock:
              - {title: 'entry 1', url: 'http://foo.bar', another_field: 'bla'}
              - {title: 'entry 2', url: 'http://foo.baz', another_field: 'bla'}
            duplicates:
              field: foo
              action: reject
    """

    def test_duplicates_accept(self, execute_task):
        task = execute_task('duplicates_accept')
        assert len(task.accepted) == 2
        assert len(task.rejected) == 0

    def test_duplicates_reject(self, execute_task):
        task = execute_task('duplicates_reject')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 1

    def test_duplicates_missing_field(self, execute_task):
        task = execute_task('duplicates_missing_field')
        assert len(task.accepted) == 0
        assert len(task.rejected) == 0
