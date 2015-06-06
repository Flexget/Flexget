from __future__ import unicode_literals, division, absolute_import

from tests import FlexGetBase


class TestCharted(FlexGetBase):
    __yaml__ = """
        tasks:
          passtrought:
            mock:
              - {title: 'passtrought music'}
            charted:
              provider: mock

          rank filter:
            mock:
              - {title: 'RANK 5', charts_mock_rank: 5}
              - {title: 'RANK 6', charts_mock_rank: 6, charts_vilain_rank: 1}
            charted:
              provider: mock
              max_rank: 5

          best rank filter:
            mock:
              - {title: 'RANK 5', charts_mock_best_rank: 5}
              - {title: 'RANK 6', charts_mock_best_rank: 6, charts_vilain_best_rank: 1}
            charted:
              provider: mock
              max_best_rank: 5

          weeks filter:
            mock:
              - {title: '5 WEEKS', charts_mock_weeks: 5, charts_vilain_weeks: 10}
              - {title: '6 WEEKS', charts_mock_weeks: 6}
            charted:
              provider: mock
              min_charted_weeks: 6

          and filter:
            mock:
              - {title: 'PASS', charts_mock_weeks: 10, charts_mock_rank: 1}
              - {title: 'TREPASS', charts_mock_weeks: 1, charts_mock_rank: 1}
            charted:
              provider: mock
              min_charted_weeks: 2
              max_rank: 10
    """

    def test_passtrought(self):
        self.execute_task('passtrought')
        assert len(self.task.accepted) == 1, "Entry filtered without any filter conditions."

    def test_rank_filtering(self):
        self.execute_task('rank filter')
        assert self.task.find_entry('entries', title='RANK 5').accepted
        assert self.task.find_entry('entries', title='RANK 6').undecided

    def test_best_rank_filtering(self):
        self.execute_task('best rank filter')
        assert self.task.find_entry('entries', title='RANK 5').accepted
        assert self.task.find_entry('entries', title='RANK 6').undecided

    def test_weeks_filtering(self):
        self.execute_task('weeks filter')
        assert self.task.find_entry('entries', title='6 WEEKS').accepted
        assert self.task.find_entry('entries', title='5 WEEKS').undecided

    def test_and_filtering(self):
        """
        We assume that ALL conditions into the filter must
        be verified to accept an entry (undecided otherwise)
        """
        self.execute_task('and filter')
        assert self.task.find_entry('entries', title='PASS').accepted
        assert self.task.find_entry('entries', title='TREPASS').undecided
