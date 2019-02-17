from __future__ import print_function

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
        l = {}
        exec(f.read(), g, l)  # pylint: disable=W0122
    if not l['__version__']:
        raise click.ClickException('Could not find __version__ from flexget/_version.py')
    return l['__version__']


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
    click.echo('current version: %s' % cur_ver)
    ver_split = cur_ver.split('.')
    if 'dev' in ver_split[-1]:
        if bump_type == 'dev':
            # If this is already a development version, increment the dev count by 1
            ver_split[-1] = 'dev%d' % (int(ver_split[-1].strip('dev') or 0) + 1)
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
                ver_split[-1] = '%sb%s' % (minor, int(beta) + 1)
            else:
                ver_split[-1] = str(int(ver_split[-1]) + 1)
        if bump_type == 'dev':
            ver_split.append('dev')
    new_version = '.'.join(ver_split)
    for line in fileinput.FileInput('flexget/_version.py', inplace=1):
        if line.startswith('__version__ ='):
            line = "__version__ = '%s'\n" % new_version
        print(line, end='')
    click.echo('new version: %s' % new_version)


@cli.command()
def bundle_webui():
    """Bundle webui for release packaging"""
    ui_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'flexget', 'ui')

    def download_extract(url, dest_path):
        print(dest_path)
        r = requests.get(url)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(dest_path)

    # WebUI V1
    click.echo('Bundle WebUI v1...')
    try:
        # Remove existing
        app_path = os.path.join(ui_path, 'v1', 'app')
        if os.path.exists(app_path):
            shutil.rmtree(app_path)
        download_extract('http://download.flexget.com/webui_v1.zip', os.path.join(ui_path, 'v1'))
    except IOError as e:
        click.echo('Unable to download and extract WebUI v1 due to %e' % str(e))
        raise click.Abort()

    # WebUI V2
    try:
        click.echo('Bundle WebUI v2...')
        # Remove existing
        app_path = os.path.join(ui_path, 'v2', 'dist')
        if os.path.exists(app_path):
            shutil.rmtree(app_path)

        release = requests.get('https://api.github.com/repos/Flexget/webui/releases/latest').json()

        v2_package = None
        for asset in release['assets']:
            if asset['name'] == 'dist.zip':
                v2_package = asset['browser_download_url']
                break

        if not v2_package:
            click.echo('Unable to find dist.zip in assets')
            raise click.Abort()
        download_extract(v2_package, os.path.join(ui_path, 'v2'))
    except (IOError, ValueError) as e:
        click.echo('Unable to download and extract WebUI v2 due to %s' % str(e))
        raise click.Abort()


@cli.command()
def autoformat():
    """Reformat code with black and isort"""
    project_root = os.path.dirname(os.path.realpath(__file__))
    venv_path = os.environ['VIRTUAL_ENV']
    if not venv_path:
        raise Exception('Virtualenv and activation required')

    subprocess.call(['black', '-S', '-l', '99', project_root])
    # isort configuration is .isort.cfg, (setup.cfg did not work for some reason)
    subprocess.call(['isort', '--virtual-env', venv_path, '-rc', project_root])


if __name__ == '__main__':
    cli()
