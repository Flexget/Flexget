# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "click~=8.1",
#     "requests~=2.32",
# ]
# ///
import fileinput
import os
import subprocess
from typing import Optional

import click
import requests

from bundle_webui import bundle_webui


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
    with fileinput.input('flexget/_version.py', inplace=True) as input:
        for line in input:
            if line.startswith('__version__ ='):
                line = f"__version__ = '{new_version}'\n"
            print(line, end='')
    click.echo(f'new version: {new_version}')


@cli.command("bundle-webui")
@click.option("--version", 'ui_version', default=None, type=click.Choice(['v2', 'v1', '']))
def cli_bundle_webui(ui_version: Optional[str] = None):
    try:
        bundle_webui(ui_version)
    except RuntimeError as exc:
        click.echo(exc.args[0], err=True)
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
