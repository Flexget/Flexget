from tests import FlexGetBase

class TestRegexp(FlexGetBase):

    __yaml__ = """
        global:
          input_mock:
            - {title: 'regexp1', 'imdb_score': 5}
            - {title: 'regexp2', 'bool_attr': true}
            - {title: 'regexp3', 'imdb_score': 5}
            - {title: 'regexp4', 'imdb_score': 5}
            - {title: 'regexp5', 'imdb_score': 5}
            - {title: 'regexp6', 'imdb_score': 5}
            - {title: 'regexp7', 'imdb_score': 5}
            - {title: 'regexp8', 'imdb_score': 5}
            - {title: 'regexp9', 'imdb_score': 5}
          seen: false

        feeds:
          # test accepting, setting custom path (both ways), test not (secondary regexp)
          test_accept:
            regexp:
              accept:
                - regexp1
                - regexp2: ~/custom_path/2/
                - regexp3:
                    path: ~/custom_path/3/
                - regexp4:
                    not:
                      - exp4

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
    """

    def test_accept(self):
        self.execute_feed('test_accept')
        assert self.feed.find_entry('accepted', title='regexp1'), 'regexp1 should have been accepted'
        assert self.feed.find_entry('accepted', title='regexp2'), 'regexp2 should have been accepted'
        assert self.feed.find_entry('accepted', title='regexp3'), 'regexp3 should have been accepted'
        assert self.feed.find_entry('entries', title='regexp4'), 'regexp4 should have been left'
        assert self.feed.find_entry('accepted', title='regexp2', path='~/custom_path/2/'), 'regexp2 should have been accepter with custom path'
        assert self.feed.find_entry('accepted', title='regexp3', path='~/custom_path/3/'), 'regexp3 should have been accepter with custom path'

    def test_reject(self):
        self.execute_feed('test_reject')
        assert self.feed.find_entry('rejected', title='regexp1'), 'regexp1 should have been rejected'

    def test_rest(self):
        self.execute_feed('test_rest')
        assert self.feed.find_entry('accepted', title='regexp1'), 'regexp1 should have been accepted'
        assert self.feed.find_entry('rejected', title='regexp3'), 'regexp3 should have been rejected'

    def test_excluding(self):
        self.execute_feed('test_excluding')
        assert not self.feed.find_entry('accepted', title='regexp1'), 'regexp1 should not have been accepted'
        assert self.feed.find_entry('accepted', title='regexp2'), 'regexp2 should have been accepted'
        assert self.feed.find_entry('accepted', title='regexp3'), 'regexp3 should have been accepted'

    def test_from(self):
        self.execute_feed('test_from')
        assert not self.feed.accepted, 'should not have accepted anything'
