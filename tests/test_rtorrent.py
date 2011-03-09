from tests import FlexGetBase
from flexget import plugin

try:
    # TODO: For meaningful tests, pyrocore must get mock support (specifically for xmlrpc)
    import pyrocore
except ImportError:
    import warnings
    warnings.warn("Some rtorrent / pyrocore tests disabled")


class TestRtorrentUnavailable(FlexGetBase):
    """Tests that can run without pyrocore installed."""

    # Note we enforce an error here if pyrocore is installed, so we can test
    # that disabling the plugin causes no unwanted calls (they'd raise).
    __tmp__ = True
    __yaml__ = """
        presets:
          global:
            rtorrent:
              enabled: no
              config_dir: __tmp__

        feeds:
          test_disabled:
            rtorrent:
              enabled: no
    """

    def test_rtorrent_disabled(self):
        "Test 'enabled' flag"
        self.execute_feed('test_disabled')

        rtorrent = plugin.get_plugin_by_name("rtorrent")
        assert rtorrent.instance.proxy is None
        assert rtorrent.instance.global_config is not None

    #def test_rtorrent_config(self):
    #    "Test different config layouts"
