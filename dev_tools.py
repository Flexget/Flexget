from __future__ import print_function

import fileinput
import os
import shutil
import subprocess

import click


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
def build_webui():
    """Build webui for release packaging"""
    cwd = os.path.join('flexget', 'ui')

    # Cleanup previous builds
    click.echo('cleaning previous builds')
    for folder in ['bower_components' 'node_modules']:
        folder = os.path.join(cwd, folder)
        if os.path.exists(folder):
            click.echo('Deleting recursively {}'.format(folder))
            shutil.rmtree(folder)

    # Install npm packages
    click.echo('running `npm install`')
    subprocess.check_call('npm install', cwd=cwd, shell=True)

    # Build the ui
    click.echo('running `bower install`')
    subprocess.check_call('bower install', cwd=cwd, shell=True)

    # Build the ui
    click.echo('running `gulp buildapp`')
    subprocess.check_call('gulp buildapp', cwd=cwd, shell=True)


if __name__ == '__main__':
    cli()
