from __future__ import unicode_literals, division, absolute_import

from flexget.plugins.clients.transmission.clean_transmission import CleanTransmissionPlugin


class TestCleanTransmissionShouldRemove:
    def _get_default_options(self, reverse=False):
        return {
            'downloaded': reverse,
            'is_directories_matching': reverse,

            'is_preserve_tracker_matching': not reverse,
            'is_tracker_matching': reverse,

            'is_clean_all': reverse,
            'is_transmission_seedlimit_unset': reverse,
            'is_transmission_seedlimit_reached': reverse,
            'is_transmission_idlelimit_reached': reverse,
            'is_minratio_reached': reverse,

            'is_torrent_seed_only': reverse,
            'is_torrent_idlelimit_since_added_reached': reverse,
            'is_torrent_idlelimit_since_finished_reached': reverse
        }

    def _get_common_mandatory_options(self, reverse_others=False):
        options = self._get_default_options(reverse=reverse_others)
        options['downloaded'] = True
        options['is_directories_matching'] = True
        options['is_preserve_tracker_matching'] = False
        options['is_tracker_matching'] = True
        return options

    def _generic_test_remove(self, options):
        return CleanTransmissionPlugin._should_remove(**options)

    def test_default_options(self):
        options = self._get_default_options()
        assert not self._generic_test_remove(options)

    def test_not_downloaded(self):
        options = self._get_default_options(reverse=True)
        options['downloaded'] = False
        assert not self._generic_test_remove(options)

    def test_not_is_directories_matching(self):
        options = self._get_default_options(reverse=True)
        options['is_directories_matching'] = False
        assert not self._generic_test_remove(options)

    def test_is_preserve_tracker_matching(self):
        options = self._get_default_options(reverse=True)
        options['is_preserve_tracker_matching'] = True
        assert not self._generic_test_remove(options)

    def test_not_is_tracker_matching(self):
        options = self._get_default_options(reverse=True)
        options['is_tracker_matching'] = False
        assert not self._generic_test_remove(options)

    # from here: downloaded = is_directories_matching = is_tracker_matching = True
    # from here: is_preserve_tracker_matching = False
    def test_get_common_mandatory_options(self):
        # Requires at least one of several conditions
        options = self._get_common_mandatory_options()
        assert not self._generic_test_remove(options)

    def test_clean_all(self):
        options = self._get_common_mandatory_options()
        options['is_clean_all'] = True
        assert self._generic_test_remove(options)

    def test_is_transmission_seedlimit_unset(self):
        options = self._get_common_mandatory_options()
        options['is_transmission_seedlimit_unset'] = True
        assert self._generic_test_remove(options)

    def test_is_transmission_seedlimit_reached(self):
        options = self._get_common_mandatory_options()
        options['is_transmission_seedlimit_reached'] = True
        assert self._generic_test_remove(options)

    def test_is_transmission_idlelimit_reached(self):
        options = self._get_common_mandatory_options()
        options['is_transmission_idlelimit_reached'] = True
        assert self._generic_test_remove(options)

    def test_is_minratio_reached(self):
        options = self._get_common_mandatory_options()
        options['is_minratio_reached'] = True
        assert self._generic_test_remove(options)

    # combinations: is_torrent_seed_only and is_torrent_idlelimit_since_added_reached
    def test_is_torrent_seed_only(self):
        options = self._get_common_mandatory_options()
        options['is_torrent_seed_only'] = True
        assert not self._generic_test_remove(options)

    def test_is_torrent_idlelimit_since_added_reached(self):
        options = self._get_common_mandatory_options()
        options['is_torrent_idlelimit_since_added_reached'] = True
        assert not self._generic_test_remove(options)

    def test_is_torrent_seed_only_and_is_torrent_idlelimit_since_added_reached(self):
        options = self._get_common_mandatory_options()
        options['is_torrent_seed_only'] = True
        options['is_torrent_idlelimit_since_added_reached'] = True
        assert self._generic_test_remove(options)

    # (remaining) combinations: not is_torrent_seed_only and is_torrent_idlelimit_since_finished_reached
    def test_is_torrent_seed_only_and_is_torrent_idlelimit_since_finished_reached(self):
        options = self._get_common_mandatory_options()
        options['is_torrent_seed_only'] = True
        options['is_torrent_idlelimit_since_finished_reached'] = True
        assert not self._generic_test_remove(options)

    def test_is_torrent_idlelimit_since_finished_reached(self):
        options = self._get_common_mandatory_options()
        options['is_torrent_idlelimit_since_finished_reached'] = True
        assert self._generic_test_remove(options)
