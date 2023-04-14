import sys
from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, colorize, console, disable_colors, table_parser

from . import db


def valid_entry(value):
    try:
        int(value)
    except ValueError:
        if value != 'all':
            raise ArgumentTypeError('Must select \'all\' or valid entry ID')
    return value


def do_cli(manager, options):
    if hasattr(options, 'table_type') and options.table_type == 'porcelain':
        disable_colors()

    if options.action == 'list':
        list_entries(options)
    elif options.action == 'approve':
        manage_entries(options, options.selection, True)
    elif options.action == 'reject':
        manage_entries(options, options.selection, False)
    elif options.action == 'clear':
        clear_entries(options)


def list_entries(options):
    """List pending entries"""
    approved = options.approved
    task_name = options.task_name

    with Session() as session:
        entries = db.list_pending_entries(session=session, task_name=task_name, approved=approved)
        header = ['#', 'Task Name', 'Title', 'URL', 'Approved', 'Added']
        table = TerminalTable(*header, table_type=options.table_type)
        for entry in entries:
            table.add_row(
                str(entry.id),
                entry.task_name,
                entry.title,
                entry.url,
                colorize('green', 'Yes') if entry.approved else 'No',
                entry.added.strftime("%c"),
            )
    console(table)


def manage_entries(options, selection, approved):
    """Manage pending entries"""
    approved_text = 'approved' if approved else 'pending'
    with Session() as session:
        if selection == 'all':
            entries = db.list_pending_entries(session=session, approved=not approved)
        else:
            try:
                entry = db.get_entry_by_id(session, selection)
                if entry.approved is approved:
                    console(
                        colorize('red', 'ERROR: ')
                        + f'Entry with ID {entry.id} is already {approved_text}'
                    )
                    sys.exit(1)
            except NoResultFound:
                console('Pending entry with ID %s does not exist' % selection)
                sys.exit(1)
            else:
                entries = [entry]
        if not entries:
            console('All entries are already %s' % approved_text)
            return
        for entry in entries:
            if entry.approved is not approved:
                console(f'Setting pending entry with ID {entry.id} status to {approved_text}')
                entry.approved = approved


def clear_entries(options):
    """Clear pending entries"""
    with Session() as session:
        query = session.query(db.PendingEntry).filter(db.PendingEntry.approved == False)
        if options.task_name:
            query = query.filter(db.PendingEntry.task_name == options.task_name)
        deleted = query.delete()
        console('Successfully deleted %i pending entries' % deleted)


@event('options.register')
def register_parser_arguments():
    selection_parser = ArgumentParser(add_help=False)
    selection_parser.add_argument(
        'selection', type=valid_entry, help='Entity ID or \'all\' to approve all pending entries'
    )

    filter_parser = ArgumentParser(add_help=False)
    filter_parser.add_argument('--task-name', help='Filter by task name')

    parser = options.register_command('pending', do_cli, help='View and manage pending entries')
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')

    list_parser = subparsers.add_parser(
        'list', help='Shows all existing pending entries', parents=[table_parser, filter_parser]
    )

    list_group = list_parser.add_mutually_exclusive_group()
    list_group.add_argument(
        '--pending',
        action='store_false',
        help='Show only pending entries',
        dest='approved',
        default=None,
    )
    list_group.add_argument(
        '--approved',
        action='store_true',
        help='Show only approved entries',
        dest='approved',
        default=None,
    )

    subparsers.add_parser('approve', help='Approve pending entries', parents=[selection_parser])
    subparsers.add_parser('reject', help='Reject pending entries', parents=[selection_parser])
    subparsers.add_parser('clear', help='Clear all pending entries', parents=[filter_parser])
