from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestMyEpisodes(FlexGetBase):
    """Uses test account at MyEpisodes, username and password are 'flexget'"""

    __yaml__ = """
        feeds:
          test:
            mock:
              - title: the.simpsons.S10E10.hdtv
            all_series: yes
            myepisodes:
              username: flexget
              password: flexget
    """

    @attr(online=True)
    def test_myepisodes_id(self):
        self.execute_feed('test')
        entry = self.feed.find_entry('accepted', title='the.simpsons.S10E10.hdtv')
        # It's tough to verify the marking worked properly, at least check that myepisodes_id is populated
        assert entry['myepisodes_id'] == '10', 'myepisodes_id should be 10 for The Simpsons'
