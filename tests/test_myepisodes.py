from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest


@pytest.mark.online
class TestMyEpisodes(object):
    """Uses test account at MyEpisodes, username and password are 'flexget'"""

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

    def test_myepisodes_id(self, execute_task):
        """Test myepisodes (DISABLED) -- account locked?"""
        return

        task = execute_task('test')
        entry = task.find_entry('accepted', title='the.simpsons.S10E10.hdtv')
        assert entry, 'entry not present'
        # It's tough to verify the marking worked properly, at least check that myepisodes_id is populated
        assert entry['myepisodes_id'] == '10', 'myepisodes_id should be 10 for The Simpsons'
