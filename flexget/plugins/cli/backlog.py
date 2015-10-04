from __future__ import unicode_literals, division, absolute_import

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.plugins.input.backlog import get_entries, clear_entries
from flexget.utils.tools import console


def do_cli(manager, options):
    if options.action == 'clear':
        num = clear_entries(options.task)
        console('%s entries cleared from backlog.' % num)
    else:
        if options.porcelain:
            cols = '{:<65.64}{:<1.1}{:<15.15}'
            console(cols.format('Title', '|', 'Task'))
        else:
            cols = '{:<65.64}{:<15.15}'
            console('-' * 80)
            console(cols.format('Title', 'Task'))
            console('-' * 80)
        with Session() as session:
            entries = get_entries(options.task, session=session)
            for entry in entries:
                if options.porcelain:
                    console(cols.format(entry.title, '|', entry.task))
                else:
                    console(cols.format(entry.title, entry.task))
            if not entries:
                console('No items')


@event('options.register')
def register_options():
    parser = options.register_command('backlog', do_cli, help='view or clear entries from backlog plugin')
    parser.add_argument('action', choices=['list', 'clear'], help='choose to show items in backlog, or clear them')
    parser.add_argument('task', nargs='?', help='limit to specific task (if supplied)')
    parser.add_argument('--porcelain', action='store_true', help='make the output parseable')
