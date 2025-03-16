import os
import platform
import shutil
from pathlib import Path

import pytest

from scripts.bundle_webui import bundle_webui


class TestBundleWebUI:
    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='The cassette generated on the Windows platform is different from the ones generated on Linux/macOS.'
        'To make the cassette generated on Linux/macOS work on the Windows platform,'
        'you need to install the zstandard dependency.',
    )
    def test_bundle_webui(self, online):
        os.environ['BUNDLE_WEBUI'] = 'true'
        v1_path = Path(__file__).parents[2] / 'flexget' / 'ui' / 'v1' / 'app'
        v2_path = Path(__file__).parents[2] / 'flexget' / 'ui' / 'v2' / 'dist'
        shutil.rmtree(v1_path, ignore_errors=True)
        shutil.rmtree(v2_path, ignore_errors=True)
        bundle_webui()
        assert v1_path.is_dir()
        assert v2_path.is_dir()
