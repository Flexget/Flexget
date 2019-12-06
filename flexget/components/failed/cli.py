from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, console, table_parser

from . import db


def do_cli(manager, options):
    if options.failed_action == 'list':
        list_failed(options)
    elif options.failed_action == 'clear':
        clear_failed(manager)


def list_failed(options):
    with Session() as session:
        results = session.query(db.FailedEntry).all()
        header = ['#', 'Title', 'Fail count', 'Reason', 'Failure time']
        table_data = [header]
        for entry in results:
            table_data.append(
                [
                    entry.id,
                    entry.title,
                    entry.count,
                    '' if entry.reason == 'None' else entry.reason,
                    entry.tof.strftime('%Y-%m-%d %H:%M'),
                ]
            )
    try:
        table = TerminalTable(options.table_type, table_data, wrap_columns=[3, 1])
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))
    else:
        table.table.justify_columns[0] = 'center'
        console(table.output)


def clear_failed(manager):
    # TODO: this should be a function in db.py
    with Session() as session:
        results = session.query(db.FailedEntry).delete()
        console('Cleared %i items.' % results)
        session.commit()
        if results:
            manager.config_changed()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('failed', do_cli, help='list or clear remembered failures')
    subparsers = parser.add_subparsers(dest='failed_action', metavar='<action>')
    subparsers.add_parser(
        'list', help='list all the entries that have had failures', parents=[table_parser]
    )
    subparsers.add_parser('clear', help='clear all failures from database, so they can be retried')
