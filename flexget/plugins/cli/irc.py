from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from argparse import ArgumentParser

from flexget import options
from flexget.event import event
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console


def do_cli(manager, options):
    """Handle irc cli"""
    action_map = {
        'status': action_status,
        'restart': action_restart,
        'stop': action_stop
    }
    from flexget.plugins.daemon.irc import irc_manager
    if irc_manager is None:
        console('IRC daemon does not appear to be running.')
        return

    action_map[options.irc_action](options, irc_manager)


def action_status(options, irc_manager):
    connection = options.irc_connection
    try:
        if connection == 'all':
            status = irc_manager.status_all()
        else:
            status = irc_manager.status(connection)
    except ValueError as e:
        console('ERROR: %s' % e.args[0])
        return

    header = ['IRC Connection', 'Thread', 'Channels', 'Connected Channels', 'Server']
    table_data = [header]
    for name, info in status.items():
        table_data.append([name, info['thread'], ', '.join(info['channels']), ', '.join(info['connected_channels']),
                           '%s:%s' % info['server']])
    table = TerminalTable(options.table_type, table_data)
    try:
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % e)


def action_restart(options, irc_manager):
    connection = options.irc_connection
    try:
        console('Restarting irc connection %s. It may take a short while.' % connection)
        if connection == 'all':
            irc_manager.restart_connections()
        else:
            irc_manager.restart_connection(connection)
        console('Successfully restarted {0}. Use `flexget irc status {0}` to check its status.'.format(connection))
    except KeyError:
        console('ERROR: %s is not a valid irc connection' % connection)


def action_stop(options, irc_manager):
    connection = options.irc_connection
    try:
        console('Stopping irc connection %s. It may take a short while.' % connection)
        if connection == 'all':
            irc_manager.stop_connections(False)
        else:
            irc_manager.stop_connection(connection)
        console('Successfully stopped {0}. Use `flexget irc status {0}` to check its status.'.format(connection))
    except KeyError:
        console('ERROR: %s is not a valid irc connection' % connection)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    irc_parser = ArgumentParser(add_help=False)
    irc_parser.add_argument('irc_connection', help="Title of the irc connection")

    # Register subcommand
    parser = options.register_command('irc', do_cli, help='View and manage irc connections')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='irc_action')
    subparsers.add_parser('status', parents=[irc_parser, table_parser], help='Shows status for specific irc connection')
    subparsers.add_parser('restart', parents=[irc_parser],
                          help='Restart an irc connection')
    subparsers.add_parser('stop', parents=[irc_parser],
                          help='Stops an irc connection')
