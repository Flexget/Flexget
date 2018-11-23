from __future__ import unicode_literals, division, absolute_import

from flexget.plugins.clients.transmission.from_transmission import FromTransmissionPlugin


started = 'started'
stopped = 'stopped'


class TestFromTransmissionShouldAdd:
    class TorrentFaker:
        def __init__(self, status):
            self.status = status

    def _generic_test_add(self, onlycomplete=True, torrent_status=started, downloaded=True, seed_ratio_ok=False,
                          idle_limit_ok=False):
        config = {'onlycomplete': onlycomplete}
        torrent = self.TorrentFaker(torrent_status)

        return FromTransmissionPlugin._should_add(config, torrent, downloaded, seed_ratio_ok, idle_limit_ok)

    # downloaded = False
    # onlycomplete = False
    def test_add_incomplete(self):
        assert self._generic_test_add(onlycomplete=False, downloaded=False)

    # downloaded = False
    # all others: onlycomplete = True
    def test_add_not_downloaded(self):
        assert not self._generic_test_add(downloaded=False, torrent_status=stopped, seed_ratio_ok=True, idle_limit_ok=True)

    # all others: downloaded = True
    def test_add_started_no_seed_info(self):
        assert not self._generic_test_add(seed_ratio_ok=None, idle_limit_ok=None)

    def test_add_stopped_no_seed_info(self):
        assert self._generic_test_add(torrent_status=stopped, seed_ratio_ok=None, idle_limit_ok=None)

    def test_add_started_seeded_ratio(self):
        assert self._generic_test_add(seed_ratio_ok=True)

    def test_add_started_seeded_time(self):
        assert self._generic_test_add(idle_limit_ok=True)

    def test_add_started_not_seeded(self):
        assert not self._generic_test_add()

    def test_add_stopped_not_seeded_time(self):
        assert not self._generic_test_add(torrent_status=stopped, idle_limit_ok=False)

    def test_add_stopped_not_seeded_ratio(self):
        assert not self._generic_test_add(torrent_status=stopped, seed_ratio_ok=False)

    def test_add_stopped_seeded_time(self):
        assert self._generic_test_add(torrent_status=stopped, idle_limit_ok=True)

    def test_add_stopped_seeded_ratio(self):
        assert self._generic_test_add(torrent_status=stopped, seed_ratio_ok=True)
