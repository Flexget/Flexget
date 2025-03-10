import pytest


@pytest.mark.online
class TestMyEpisodes:
    """Use test account at MyEpisodes, username and password are 'flexget'."""

    config = """
        tasks:
          test:
            mock:
              - title: the.simpsons.S10E10.hdtv
            all_series: yes
            myepisodes:
              username: flexget
              password: flexget
    """

    @pytest.mark.skip(reason="Test myepisodes (DISABLED) -- account locked?")
    def test_myepisodes_id(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry('accepted', title='the.simpsons.S10E10.hdtv')
        assert entry, 'entry not present'
        # It's tough to verify the marking worked properly, at least check that myepisodes_id is populated
        assert entry['myepisodes_id'] == '10', 'myepisodes_id should be 10 for The Simpsons'
