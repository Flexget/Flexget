from tests import FlexGetBase
from flexget.plugins.api_tvrage import lookup_series
import logging

log = logging.getLogger('TestTvRage')

class TestTvRage(FlexGetBase):

    def test_setdefault(self):
        friends = lookup_series("Friends")
        s1e22 = friends.episode(1,22)
        log.info("s1e22 %s " % s1e22)

        # Testing next
        s1e23 = s1e22.next()
        log.info("s1e23 %s " % s1e23)
        assert s1e23.epnum == 23 and s1e23.seasonnum == 1
        
        s1e24 = s1e23.next()
        assert s1e24.epnum == 24 and s1e24.seasonnum == 1
        log.info("s1e24 %s " % s1e24)
        
        s2e1 = s1e24.next()
        assert s2e1.epnum == 1 and s2e1.seasonnum == 2
        log.info("s2e1 %s " % s2e1)
        
        s31e1 = friends.episode(31,1)
        assert not s31e1
        log.info("s31e1 %s " % s31e1)
        s1e1 = friends.episode(1,1)
        assert s1e1
        log.info("s1e1 %s " % s1e1)
        s1e32 = friends.episode(1,32)
        log.info("s1e32 %s " % s1e32)
        assert not s1e32
        assert friends.finnished()
