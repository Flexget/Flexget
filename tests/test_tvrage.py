from __future__ import unicode_literals, division, absolute_import
import logging

from nose.plugins.attrib import attr

from tests import FlexGetBase
from flexget.plugins.api_tvrage import lookup_series

log = logging.getLogger('TestTvRage')


class TestTvRage(FlexGetBase):

    @attr(online=True)
    def test_tvrage(self):
        friends = lookup_series("Friends")
        assert friends.genres == ['Comedy', 'Romance/Dating']
        s1e22 = friends.find_episode(1, 22)
        log.info("s1e22 %s " % s1e22)

        # Testing next
        s1e23 = s1e22.next()
        log.info("s1e23 %s " % s1e23)
        assert s1e23.episode == 23 and s1e23.season == 1

        s1e24 = s1e23.next()
        assert s1e24.episode == 24 and s1e24.season == 1
        log.info("s1e24 %s " % s1e24)

        s2e1 = s1e24.next()
        assert s2e1.episode == 1 and s2e1.season == 2
        log.info("s2e1 %s " % s2e1)

        s31e1 = friends.find_episode(31, 1)
        assert not s31e1
        log.info("s31e1 %s " % s31e1)
        s1e1 = friends.find_episode(1, 1)
        assert s1e1
        log.info("s1e1 %s " % s1e1)
        s1e32 = friends.find_episode(1 ,32)
        log.info("s1e32 %s " % s1e32)
        assert not s1e32
        assert friends.finished()
