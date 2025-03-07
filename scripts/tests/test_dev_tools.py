import os
import platform
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from scripts.dev_tools import bump_version, cli_bundle_webui, get_changelog, version


class TestDevTools:
    def test_version(self, tmp_path):
        os.makedirs(tmp_path / 'flexget', exist_ok=True)
        shutil.copy(
            Path(__file__).parent / 'dev_tools' / 'dev_version.py',
            tmp_path / 'flexget' / '_version.py',
        )
        os.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(version)
        assert result.exit_code == 0
        assert result.output == '3.13.19.dev\n'

    @pytest.mark.parametrize(
        ('bump_from', 'bump_to', 'version'),
        [
            (
                'dev',
                'release',
                '3.13.19',
            ),
            (
                'release',
                'dev',
                '3.13.20.dev',
            ),
        ],
    )
    def test_bump_version(self, tmp_path, bump_from, bump_to, version):
        os.makedirs(tmp_path / 'flexget', exist_ok=True)
        shutil.copy(
            Path(__file__).parent / 'dev_tools' / f'{bump_from}_version.py',
            tmp_path / 'flexget' / '_version.py',
        )
        os.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(bump_version, [bump_to])
        assert result.exit_code == 0
        with open(tmp_path / 'flexget' / '_version.py') as f:
            assert f"__version__ = '{version}'\n" in f

    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='The cassette generated on the Windows platform is different from the ones generated on Linux/macOS.'
        'To make the cassette generated on Linux/macOS work on the Windows platform,'
        'you need to install the zstandard dependency.',
    )
    @pytest.mark.parametrize(
        'args', [[], ['--version', 'v2'], ['--version', 'v1'], ['--version', '']]
    )
    def test_cli_bundle_webui(self, args, online):
        os.environ['BUNDLE_WEBUI'] = 'true'
        v1_path = Path(__file__).parent.parent.parent / 'flexget' / 'ui' / 'v1' / 'app'
        v2_path = Path(__file__).parent.parent.parent / 'flexget' / 'ui' / 'v2' / 'dist'
        shutil.rmtree(v1_path, ignore_errors=True)
        shutil.rmtree(v2_path, ignore_errors=True)
        runner = CliRunner()
        result = runner.invoke(cli_bundle_webui, args)
        assert result.exit_code == 0
        if 'v1' in args:
            assert v1_path.is_dir()
        elif 'v2' in args:
            assert v2_path.is_dir()
        else:
            assert v1_path.is_dir()
            assert v2_path.is_dir()

    @pytest.mark.skipif(
        platform.system() == 'Windows',
        reason='The cassette generated on the Windows platform is different from the ones generated on Linux/macOS.'
        'To make the cassette generated on Linux/macOS work on the Windows platform,'
        'you need to install the zstandard dependency.',
    )
    def test_get_changelog(self, online):
        runner = CliRunner()
        result = runner.invoke(get_changelog, ['v3.13.6'])
        assert result.exit_code == 0
        assert result.output == (
            '[all commits](https://github.com/Flexget/Flexget/compare/v3.13.5...v3.13.6)\n'
            '### Changed\n'
            '- Strictly ignore 19xx-20xx from episode parsing\n'
            '- Strictly ignore 19xx-20xx from episode parsing\n'
        )
