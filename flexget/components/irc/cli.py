from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from argparse import ArgumentParser

from colorclass.toggles import disable_all_colors
from flexget import options
from flexget.event import event
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console, colorize

try:
    from irc_bot.simple_irc_bot import IRCChannelStatus, SimpleIRCBot
except ImportError:
    SimpleIRCBot = None
    IRCChannelStatus = None


def do_cli(manager, options):
    """Handle irc cli"""

    if SimpleIRCBot is None:
        console('irc_bot is not installed. install using `pip install irc_bot`.')
        return

    if hasattr(options, 'table_type') and options.table_type == 'porcelain':
        disable_all_colors()

    action_map = {'status': action_status, 'restart': action_restart, 'stop': action_stop}

    # NOTE: Direct importing of other plugins is discouraged
    from flexget.components.irc.irc import irc_manager

    if irc_manager is None:
        console('IRC daemon does not appear to be running.')
        return

    action_map[options.irc_action](options, irc_manager)


def action_status(options, irc_manager):
    connection = options.irc_connection
    try:
        status = irc_manager.status(connection)
    except ValueError as e:
        console('ERROR: %s' % e.args[0])
        return

    header = ['Name', 'Alive', 'Channels', 'Server']
    table_data = [header]

    for connection in status:
        for name, info in connection.items():
            alive = colorize('green', 'Yes') if info['alive'] else colorize('red', 'No')
            channels = []
            for channel in info['channels']:
                for channel_name, channel_status in channel.items():
                    channels.append(channel_name)
                    if channel_status == IRCChannelStatus.CONNECTED:
                        channels[-1] = colorize('green', '* ' + channels[-1])
            table_data.append(
                [name, alive, ', '.join(channels), '%s:%s' % (info['server'], info['port'])]
            )
    try:
        table = TerminalTable(options.table_type, table_data)
        console(table.output)
        console(colorize('green', ' * Connected channel'))
    except TerminalTableError as e:
        console('ERROR: %s' % e)


def action_restart(options, irc_manager):
    connection = options.irc_connection
    try:
        console('Restarting irc connection %s. It may take a short while.' % connection)
        irc_manager.restart_connections(connection)
        console(
            'Successfully restarted {0}. Use `flexget irc status {0}` to check its status.'.format(
                connection or 'all'
            )
        )
    except KeyError:
        console('ERROR: %s is not a valid irc connection' % connection)


def action_stop(options, irc_manager):
    connection = options.irc_connection
    try:
        console('Stopping irc connection %s. It may take a short while.' % connection)
        irc_manager.stop_connections(wait=False, name=connection)
        console(
            'Successfully stopped {0}. Use `flexget irc status {0}` to check its status.'.format(
                connection or 'all'
            )
        )
    except KeyError:
        console('ERROR: %s is not a valid irc connection' % connection)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    irc_parser = ArgumentParser(add_help=False)
    irc_parser.add_argument('irc_connection', nargs='?', help="Title of the irc connection")

    # Register subcommand
    parser = options.register_command('irc', do_cli, help='View and manage irc connections')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='irc_action')
    subparsers.add_parser(
        'status',
        parents=[irc_parser, table_parser],
        help='Shows status for specific irc connection',
    )
    subparsers.add_parser('restart', parents=[irc_parser], help='Restart an irc connection')
    subparsers.add_parser('stop', parents=[irc_parser], help='Stops an irc connection')
