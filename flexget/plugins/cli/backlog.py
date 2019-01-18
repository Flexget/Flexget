from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.plugins.input import backlog as plugin_backlog
except ImportError:
    raise plugin.DependencyError(
        issued_by=__name__, missing='backlog',
    )


def do_cli(manager, options):
    if options.action == 'clear':
        num = plugin_backlog.clear_entries(options.task, all=True)
        console('%s entries cleared from backlog.' % num)
    else:
        header = ['Title', 'Task', 'Expires']
        table_data = [header]
        with Session() as session:
            entries = plugin_backlog.get_entries(options.task, session=session)
            for entry in entries:
                table_data.append([entry.title, entry.task, entry.expire.strftime('%Y-%m-%d %H:%M')])
        try:
            table = TerminalTable(options.table_type, table_data, wrap_columns=[0])
            console(table.output)
        except TerminalTableError as e:
            console('ERROR: %s' % str(e))


@event('options.register')
def register_options():
    parser = options.register_command('backlog', do_cli, help='View or clear entries from backlog plugin',
                                      parents=[table_parser])
    parser.add_argument('action', choices=['list', 'clear'],
                        help='Choose to show items in backlog, or clear all of them')
    parser.add_argument('task', nargs='?', help='Limit to specific task (if supplied)')
