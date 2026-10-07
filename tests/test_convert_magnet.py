import sys

import pytest


@pytest.mark.skip(reason='This test requires real network access and is therefore unstable')
@pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason='libtorrent does not provide wheels for Python 3.14+.',
)
@pytest.mark.require_optional_deps
class TestConvertMagnet:
    config = """
        tasks:
          convert_magnet:
            accept_all: yes
            mock:
              - { title: "ubuntu-26.04", url: "magnet:?xt=urn:btih:5b1e0d988fc7a0c9e99bd852071681a59974b39f" }
            convert_magnet: yes
    """

    def test_convert_magnet(self, execute_task, manager):
        execute_task('convert_magnet')
        assert (
            manager.config_base / 'converted' / 'ubuntu-26.04.1-desktop-amd64.iso.torrent'
        ).exists()
