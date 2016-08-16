from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import argparse
from datetime import datetime, timedelta

from flexget import options, plugin
from flexget.event import event
from flexget.terminal import console
from flexget.manager import Session

def do_cli(manager, options):
    console('hello')



@event('options.register')
def register_parser_arguments():
    # Register the command
    parser = options.register_command('search', do_cli, help='Test search features. Useful for development & testing.')

    # Parent parser for subcommands that need a series name
    series_parser = argparse.ArgumentParser(add_help=False)
    series_parser.add_argument('series_name', help='the name of the series', metavar='<series name>')

    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')
    list_parser = subparsers.add_parser('list', help='list a summary of the different series being tracked')
    list_parser.add_argument('configured', nargs='?', choices=['configured', 'unconfigured', 'all'],
                             default='configured',
                             help='limit list to series that are currently in the config or not (default: %(default)s)')
    list_parser.add_argument('--premieres', action='store_true',
                             help='limit list to series which only have episode 1 (and maybe also 2) downloaded')
    list_parser.add_argument('--new', nargs='?', type=int, metavar='DAYS', const=7,
                             help='limit list to series with a release seen in last %(const)s days. number of days can '
                                  'be overridden with %(metavar)s')
    list_parser.add_argument('--stale', nargs='?', type=int, metavar='DAYS', const=365,
                             help='limit list to series which have not seen a release in %(const)s days. number of '
                                  'days can be overridden with %(metavar)s')
    list_parser.add_argument('--porcelain', action='store_true', help='make the output parseable')

    subparsers.add_parser('show', parents=[series_parser],
                                        help='show the releases FlexGet has seen for a given series ')
    begin_parser = subparsers.add_parser('begin', parents=[series_parser],
                                         help='set the episode to start getting a series from')
    begin_parser.add_argument('episode_id', metavar='<episode ID>',
                              help='episode ID to start getting the series from (e.g. S02E01, 2013-12-11, or 9, '
                                   'depending on how the series is numbered)')
    forget_parser = subparsers.add_parser('forget', parents=[series_parser],
                                          help='removes episodes or whole series from the entire database '
                                               '(including seen plugin)')
    forget_parser.add_argument('episode_id', nargs='?', default=None, help='episode ID to forget (optional)')
    delete_parser = subparsers.add_parser('remove', parents=[series_parser],
                                          help='removes episodes or whole series from the series database only')
    delete_parser.add_argument('episode_id', nargs='?', default=None, help='episode ID to forget (optional)')
