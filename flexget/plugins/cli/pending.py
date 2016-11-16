from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from argparse import ArgumentTypeError

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.plugins.filter.pending_approval import list_pending_entries, get_entry_by_id
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console, colorize
from colorclass.toggles import disable_all_colors
from sqlalchemy.orm.exc import NoResultFound


def valid_entry(value):
    try:
        int(value)
    except ValueError:
        if value != 'all':
            raise ArgumentTypeError('Must select \'all\' or valid entry ID')
    return value


def do_cli(manager, options):
    if hasattr(options, 'table_type') and options.table_type == 'porcelain':
        disable_all_colors()
    action_map = {
        'list': list_entries,
        'approve': approve_entries
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


def approve_entries(options):
    """Approved pending entries"""
    approve = options.approve
    with Session() as session:
        if approve == 'all':
            entries = list_pending_entries(session=session, approved=False)
        else:
            try:
                entry = get_entry_by_id(session, approve)
                if entry.approved is True:
                    console('ERROR: Entry with ID %s is already approved' % entry.id)
                    sys.exit(1)
            except NoResultFound:
                console('Pending entry with ID %s does not exist' % approve)
                sys.exit(1)
            else:
                entries = [entry]
        for entry in entries:
            if entry.approved is False:
                console('Setting pending entry with ID %s status to approved' % entry.id)
                entry.approved = True


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('pending', do_cli, help='View and pending')
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')

    list_parser = subparsers.add_parser('list', help='Shows all existing pending entries', parents=[table_parser])
    list_parser.add_argument('--task-name', help='Filter by task name')
    list_group = list_parser.add_mutually_exclusive_group()
    list_group.add_argument('--pending', action='store_false', help='Show only pending entries', dest='approved',
                            default=None)
    list_group.add_argument('--approved', action='store_true', help='Show only approved entries', dest='approved',
                            default=None)

    approve_parser = subparsers.add_parser('approve', help='Approved pending entries')
    approve_parser.add_argument('approve', type=valid_entry, help='Entity ID or \'all\' to approve all pending entries')
