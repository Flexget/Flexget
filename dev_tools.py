from __future__ import unicode_literals, print_function
import fileinput
import sys

import click


@click.group()
def cli():
    pass


@cli.command()
@click.argument('bump_type', type=click.Choice(['dev', 'release']))
def bump_version(bump_type):
    """Bumps version to the next release, or development version."""
    __version__ = None
    with open('flexget/_version.py') as f:
        exec(f.read())
    if not __version__:
        print('Could not find __version__ from flexget/_version.py')
        sys.exit(1)
    print('current version: %s' % __version__)
    ver_split = __version__.split('.')
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
            ver_split[-1] = str(int(ver_split[-1]) + 1)
        if bump_type == 'dev':
            ver_split.append('dev')
    new_version = '.'.join(ver_split)
    for line in fileinput.FileInput('flexget/_version.py', inplace=1):
        if line.startswith('__version__ ='):
            line = "__version__ = '%s'\n" % new_version
        print(line, end='')
    print('new version: %s' % new_version)
