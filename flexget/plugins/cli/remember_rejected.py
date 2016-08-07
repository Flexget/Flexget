from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from functools import partial

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugins.filter.remember_rejected import RememberEntry
from flexget.terminal import TerminalTable, CLITableError, table_parser


def do_cli(manager, options):
    if options.rejected_action == 'list':
        list_rejected(options)
    elif options.rejected_action == 'clear':
        clear_rejected(manager)


def list_rejected(options):
    ww = partial(TerminalTable.word_wrap, max_length=options.max_column_width)
    with Session() as session:
        results = session.query(RememberEntry).all()
        header = ['#', 'Title', 'Task', 'Rejected by', 'Reason']
        table_data = [header]
        for entry in results:
            table_data.append([entry.id, ww(entry.title), entry.task.name, entry.rejected_by, entry.reason or ''])
    table = TerminalTable(options.table_type, table_data, check_size=options.check_size)
    table.table.justify_columns[0] = 'center'
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))


def clear_rejected(manager):
    with Session() as session:
        results = session.query(RememberEntry).delete()
        console('Cleared %i items.' % results)
        session.commit()
        if results:
            manager.config_changed()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('rejected', do_cli, help='list or clear remembered rejections')
    subparsers = parser.add_subparsers(dest='rejected_action', metavar='<action>')
    subparsers.add_parser('list', help='list all the entries that have been rejected', parents=[table_parser])
    subparsers.add_parser('clear', help='clear all rejected entries from database, so they can be retried')
