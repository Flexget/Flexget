from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from nose.plugins.attrib import attr


class TestMyEpisodes(FlexGetBase):
    """Uses test account at MyEpisodes, username and password are 'flexget'"""

    __yaml__ = """
        tasks:
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
        """Test myepisodes (DISABLED) -- account locked?"""
        return

        self.execute_task('test')
        entry = self.task.find_entry('accepted', title='the.simpsons.S10E10.hdtv')
        assert entry, 'entry not present'
        # It's tough to verify the marking worked properly, at least check that myepisodes_id is populated
        assert entry['myepisodes_id'] == '10', 'myepisodes_id should be 10 for The Simpsons'
