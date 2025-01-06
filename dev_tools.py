# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click~=8.1",
#     "requests~=2.32",
# ]
# ///
import fileinput
import io
import os
import shutil
import subprocess
import zipfile

import click
import requests


def _get_version():
    with open('flexget/_version.py') as f:
        g = globals()
        loc = {}
        exec(f.read(), g, loc)
    if not loc['__version__']:
        raise click.ClickException('Could not find __version__ from flexget/_version.py')
    return loc['__version__']


@click.group()
def cli():
    pass


@cli.command()
def version():
    """Prints the version number of the source"""
    click.echo(_get_version())


@cli.command()
@click.argument('bump_type', type=click.Choice(['dev', 'release']))
def bump_version(bump_type):
    """Bumps version to the next release, or development version."""
    cur_ver = _get_version()
    click.echo(f'current version: {cur_ver}')
    ver_split = cur_ver.split('.')
    if 'dev' in ver_split[-1]:
        if bump_type == 'dev':
            # If this is already a development version, increment the dev count by 1
            ver_split[-1] = 'dev{}'.format(int(ver_split[-1].strip('dev') or 0) + 1)
        else:
            # Just strip off dev tag for next release version
            ver_split = ver_split[:-1]
    else:
        # Increment the revision number by one
        if len(ver_split) == 2:
            # We don't have a revision number, assume 0
            ver_split.append('1')
        else:
            if 'b' in ver_split[2]:
                # beta version
                minor, beta = ver_split[-1].split('b')
                ver_split[-1] = f'{minor}b{int(beta) + 1}'
            else:
                ver_split[-1] = str(int(ver_split[-1]) + 1)
        if bump_type == 'dev':
            ver_split.append('dev')
    new_version = '.'.join(ver_split)
    for line in fileinput.FileInput('flexget/_version.py', inplace=1):
        if line.startswith('__version__ ='):
            line = f"__version__ = '{new_version}'\n"
        print(line, end='')
    click.echo(f'new version: {new_version}')


@cli.command()
@click.option("--version", 'ui_version', default='', type=click.Choice(['v2', 'v1', '']))
def bundle_webui(ui_version: str = ""):
    """Bundle webui for release packaging"""
    ui_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'flexget', 'ui')

    def download_extract(url, dest_path):
        print(dest_path)
        r = requests.get(url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(dest_path)

    if ui_version in ['', 'v1']:
        # WebUI V1
        click.echo('Bundle WebUI v1...')
        try:
            # Remove existing
            app_path = os.path.join(ui_path, 'v1', 'app')
            if os.path.exists(app_path):
                shutil.rmtree(app_path)
            # Just stashed the old webui zip on a random github release for easy hosting.
            # It doesn't get updated anymore,
            # we should probably stop bundling it with releases soon.
            download_extract(
                'https://github.com/Flexget/Flexget/releases/download/v3.0.6/webui_v1.zip',
                os.path.join(ui_path, 'v1'),
            )
        except OSError as e:
            click.echo(f'Unable to download and extract WebUI v1 due to {e!s:e}')
            raise click.Abort()

    if ui_version in ['', 'v2']:
        # WebUI V2
        try:
            click.echo('Bundle WebUI v2...')
            # Remove existing
            app_path = os.path.join(ui_path, 'v2', 'dist')
            if os.path.exists(app_path):
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
                click.echo('Unable to find dist.zip in assets')
                raise click.Abort()
            download_extract(v2_package, os.path.join(ui_path, 'v2'))
        except (OSError, ValueError) as e:
            click.echo(f'Unable to download and extract WebUI v2 due to {e!s}')
            raise click.Abort()


@cli.command()
@click.argument('files', nargs=-1)
def autoformat(files):
    """Reformat code with Ruff"""
    if not files:
        project_root = os.path.dirname(os.path.realpath(__file__))
        files = (project_root,)
    venv_path = os.environ['VIRTUAL_ENV']
    if not venv_path:
        raise Exception('Virtualenv and activation required')

    # ruff config is in pyproject.toml
    subprocess.call(('ruff', 'check', '--fix', *files))
    subprocess.call(('ruff', 'format', *files))


@cli.command()
@click.argument('version')
def get_changelog(version):
    version = version.lstrip("v")
    changelog_lines = []
    with requests.get(
        "https://raw.githubusercontent.com/Flexget/wiki/main/ChangeLog.md", stream=True
    ) as resp:
        lines = resp.iter_lines(decode_unicode=True)
        for line in lines:
            if line.startswith(f"## {version}"):
                break
        else:
            click.echo(f"Could not find version {version} in changelog", err=True)
            return
        for line in lines:
            if line.startswith("## ") or line.startswith("<!---"):
                break
            changelog_lines.append(line)
    click.echo("\n".join(changelog_lines).strip())


if __name__ == '__main__':
    cli()
