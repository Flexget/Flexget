from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugins.input.backlog import get_entries, clear_entries
from flexget.terminal import TerminalTable, CLITableError, table_parser


def do_cli(manager, options):
    if options.action == 'clear':
        num = clear_entries(options.task)
        console('%s entries cleared from backlog.' % num)
    else:
        header = ['Title', 'Task', 'Expires']
        table_data = [header]
        with Session() as session:
            entries = get_entries(options.task, session=session)
            for entry in entries:
                table_data.append([entry.title, entry.task, entry.expire])
        table = TerminalTable(options.table_type, table_data, wrap_columns=[(0, 100)])
        try:
            console(table.output)
        except CLITableError as e:
            console('ERROR: %s' % str(e))


@event('options.register')
def register_options():
    parser = options.register_command('backlog', do_cli, help='view or clear entries from backlog plugin',
                                      parents=[table_parser])
    parser.add_argument('action', choices=['list', 'clear'], help='choose to show items in backlog, or clear them')
    parser.add_argument('task', nargs='?', help='limit to specific task (if supplied)')
