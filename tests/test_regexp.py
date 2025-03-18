class TestRegexp:
    config = """
        templates:
          global:
            mock:
              - {title: 'regexp1', 'imdb_score': 5}
              - {title: 'regexp2', 'bool_attr': true}
              - {title: 'regexp3', 'imdb_score': 5}
              - {title: 'regexp4', 'imdb_score': 5}
              - {title: 'regexp5', 'imdb_score': 5}
              - {title: 'regexp6', 'imdb_score': 5}
              - {title: 'regexp7', 'imdb_score': 5}
              - {title: 'regexp8', 'imdb_score': 5}
              - {title: 'regexp9', 'imdb_score': 46}
              - {title: 'regular', otherfield: 'genre1', genre: ['genre2', 'genre3']}
              - {title: 'expression', genre: ['genre1', 'genre2']}
            seen: false

        tasks:
          # test accepting, setting custom path (both ways), test not (secondary regexp)
          test_accept:
            regexp:
              accept:
                - regexp1
                - regexp2: '~'
                - regexp3:
                    path: '~'
                - regexp4:
                    not:
                      - exp4
                - regexp5:
                    not: exp7

          # test rejecting
          test_reject:
            regexp:
              reject:
                - regexp1

          # test rest
          test_rest:
            regexp:
              accept:
                - regexp1
              rest: reject

          test_rest2:
            template: no_global
            mock:
            - title: accept
            regexp:
              accept:
              - accept
              reject:
              - reject
              rest: reject

          test_only_rest:
            regexp:
              rest: reject

          # test excluding
          test_excluding:
            regexp:
              accept_excluding:
                - regexp1

          # test from
          test_from:
            regexp:
              accept:
                - localhost:
                    from:
                      - title

          test_multiple_excluding:
            regexp:
              reject_excluding:
                - reg
                - exp
                - '5'
              rest: accept

          # test complicated
          test_complicated:
            regexp:
              accept:
                - regular
                - regexp9
              accept_excluding:
                - reg
                - exp5
              rest: reject

          test_numeric:
            regexp:
              accept:
                - 6:
                    from: imdb_score

          test_match_in_list:
            regexp:
              # Also tests global from option
              from: genre
              accept:
                - genre1
                - genre2:
                    not: genre3
    """

    def test_accept(self, execute_task):
        task = execute_task('test_accept')
        assert task.find_entry('accepted', title='regexp1'), 'regexp1 should have been accepted'
        assert task.find_entry('accepted', title='regexp2'), 'regexp2 should have been accepted'
        assert task.find_entry('accepted', title='regexp3'), 'regexp3 should have been accepted'
        assert task.find_entry('entries', title='regexp4') not in task.accepted, (
            'regexp4 should have been left'
        )
        assert task.find_entry('accepted', title='regexp2', path='~'), (
            'regexp2 should have been accepter with custom path'
        )
        assert task.find_entry('accepted', title='regexp3', path='~'), (
            'regexp3 should have been accepter with custom path'
        )
        assert task.find_entry('accepted', title='regexp5'), 'regexp5 should have been accepted'

    def test_reject(self, execute_task):
        task = execute_task('test_reject')
        assert task.find_entry('rejected', title='regexp1'), 'regexp1 should have been rejected'

    def test_rest(self, execute_task):
        task = execute_task('test_rest')
        assert task.find_entry('accepted', title='regexp1'), 'regexp1 should have been accepted'
        assert task.find_entry('rejected', title='regexp3'), 'regexp3 should have been rejected'

    def test_rest2(self, execute_task):
        task = execute_task('test_rest2')
        assert task.find_entry('accepted', title='accept'), 'regexp1 should have been accepted'

    def test_only_rest(self, execute_task):
        task = execute_task('test_only_rest')
        assert len(task.all_entries) == len(task.rejected), 'all entries should have been rejected'

    def test_excluding(self, execute_task):
        task = execute_task('test_excluding')
        assert not task.find_entry('accepted', title='regexp1'), (
            'regexp1 should not have been accepted'
        )
        assert task.find_entry('accepted', title='regexp2'), 'regexp2 should have been accepted'
        assert task.find_entry('accepted', title='regexp3'), 'regexp3 should have been accepted'

    def test_from(self, execute_task):
        task = execute_task('test_from')
        assert not task.accepted, 'should not have accepted anything'

    def test_multiple_excluding(self, execute_task):
        task = execute_task('test_multiple_excluding')
        assert task.find_entry('rejected', title='regexp2'), (
            '\'regexp2\' should have been rejected'
        )
        assert task.find_entry('rejected', title='regexp7'), (
            '\'regexp7\' should have been rejected'
        )
        assert task.find_entry('accepted', title='regexp5'), (
            '\'regexp5\' should have been accepted'
        )

    def test_complicated(self, execute_task):
        task = execute_task('test_complicated')
        assert task.find_entry('accepted', title='regular'), (
            '\'regular\' should have been accepted'
        )
        assert task.find_entry('accepted', title='expression'), (
            '\'expression\' should have been accepted'
        )
        assert task.find_entry('accepted', title='regexp9'), (
            '\'regexp9\' should have been accepted'
        )
        assert task.find_entry('rejected', title='regexp5'), (
            '\'regexp5\' should have been rejected'
        )

    def test_numeric(self, execute_task):
        task = execute_task('test_numeric')
        msg = '\'regexp9\' should have been accepted because of score regexp'
        assert task.find_entry('accepted', title='regexp9'), msg
        msg = '\'regexp8\' should NOT have been accepted because of score regexp'
        assert not task.find_entry('accepted', title='regexp8'), msg

    def test_match_in_list(self, execute_task):
        task = execute_task('test_match_in_list')
        assert task.find_entry('accepted', title='expression'), (
            '\'expression\' should have been accepted'
        )
        assert task.find_entry('entries', title='regular') not in task.accepted, (
            '\'regular\' should not have been accepted'
        )
