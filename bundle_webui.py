# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests",
# ]
# ///
import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional

# If hatchling is available (like in the build environment) this file provides
# a hook for bundling the webui into our wheel release.
try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ImportError:
    pass
else:

    class CustomBuildHook(BuildHookInterface):
        PLUGIN_NAME = "bundle-webui"

        def dependencies(self) -> list[str]:
            if os.environ.get("BUNDLE_WEBUI") not in ["1", "true"]:
                return []
            return ["requests"]

        def clean(self, versions: list[str]) -> None:
            p = Path(__file__).resolve().parent
            v1_path = p / "flexget" / "ui" / "v1" / "app"
            v2_path = p / "flexget" / "ui" / "v2" / "dist"
            if v1_path.exists():
                shutil.rmtree(v1_path)
            if v2_path.exists():
                shutil.rmtree(v2_path)

        def initialize(self, version: str, build_data: dict[str, Any]) -> None:
            if os.environ.get("BUNDLE_WEBUI") not in ["1", "true"]:
                return
            bundle_webui()
            build_data["force_include"]["flexget/ui/v1/app"] = "/flexget/ui/v1/app"
            build_data["force_include"]["flexget/ui/v2/dist"] = "/flexget/ui/v2/dist"


def bundle_webui(ui_version: Optional[str] = None):
    """Bundle webui for release packaging."""
    # We delay this import so that the hatchling build hook can register itself without requests installed.
    # once it is registered it can install the dep automatically during the build process.
    import requests

    ui_path = Path(__file__).resolve().parent / "flexget" / "ui"

    def download_extract(url, dest_path):
        print(dest_path)
        r = requests.get(url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(dest_path)

    if not ui_version or ui_version == 'v1':
        # WebUI V1
        print('Bundling WebUI v1...')
        try:
            # Remove existing
            app_path = ui_path / "v1" / "app"
            if app_path.exists():
                shutil.rmtree(app_path)
            # Just stashed the old webui zip on a random github release for easy hosting.
            # It doesn't get updated anymore,
            # we should probably stop bundling it with releases soon.
            download_extract(
                'https://github.com/Flexget/Flexget/releases/download/v3.0.6/webui_v1.zip',
                ui_path / "v1",
            )
        except OSError as e:
            raise RuntimeError(f'Unable to download and extract WebUI v1 due to {e!s}')

    if not ui_version or ui_version == 'v2':
        # WebUI V2
        try:
            print('Bundling WebUI v2...')
            # Remove existing
            app_path = ui_path / "v2" / "dist"
            if app_path.exists():
                shutil.rmtree(app_path)

            release = requests.get(
                'https://api.github.com/repos/Flexget/webui/releases/latest'
            ).json()

            v2_package = None
            for asset in release['assets']:
                if asset['name'] == 'dist.zip':
                    v2_package = asset['browser_download_url']
                    break

            if not v2_package:
                raise RuntimeError('Unable to find dist.zip in assets')
            download_extract(v2_package, ui_path / "v2")
        except (OSError, ValueError) as e:
            raise RuntimeError(f'Unable to download and extract WebUI v2 due to {e!s}')


if __name__ == '__main__':
    bundle_webui()
