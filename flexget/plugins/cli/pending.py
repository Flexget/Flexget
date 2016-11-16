from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.plugins.filter.pending_approval import list_pending_entries
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console, colorize
from colorclass.toggles import disable_all_colors


def do_cli(manager, options):
    if hasattr(options, 'table_type') and options.table_type == 'porcelain':
        disable_all_colors()
    action_map = {
        'list': list_entries
    }
    action_map[options.action](options)


def list_entries(options):
    """List pending entries"""
    approved = options.approved
    task_name = options.task_name

    with Session() as session:
        entries = list_pending_entries(session=session, task_name=task_name, approved=approved)
        header = ['#', 'Task Name', 'Title', 'URL', 'Approved', 'Added']
        table_data = [header]
        for entry in entries:
            table_data.append([
                entry.id,
                entry.task_name,
                entry.title,
                entry.url,
                colorize('green', 'Yes') if entry.approved else 'No',
                entry.added.strftime("%c"),
            ])
        table = TerminalTable(options.table_type, table_data, wrap_columns=[2, 1, 0], drop_columns=[4, 2])
        try:
            console(table.output)
        except TerminalTableError as e:
            console('ERROR: %s' % str(e))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('pending', do_cli, help='View and pending')
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')

    list_parser = subparsers.add_parser('list', help='Shows all existing pending entries', parents=[table_parser])
    list_parser.add_argument('--task-name', help='Filter by task name')
    group = list_parser.add_mutually_exclusive_group()
    group.add_argument('--pending', action='store_false', help='Show only pending entries', dest='approved',
                       default=None)
    group.add_argument('--approved', action='store_true', help='Show only approved entries', dest='approved',
                       default=None)
