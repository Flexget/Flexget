import os
import shutil
from pathlib import Path

from scripts.bundle_webui import bundle_webui


class TestBundleWebUI:
    def test_bundle_webui(self, online):
        os.environ['BUNDLE_WEBUI'] = 'true'
        v1_path = Path(__file__).parents[2] / 'flexget' / 'ui' / 'v1' / 'app'
        v2_path = Path(__file__).parents[2] / 'flexget' / 'ui' / 'v2' / 'dist'
        shutil.rmtree(v1_path, ignore_errors=True)
        shutil.rmtree(v2_path, ignore_errors=True)
        bundle_webui()
        assert v1_path.is_dir()
        assert v2_path.is_dir()
