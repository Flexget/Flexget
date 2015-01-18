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
        with Session() as session:
            cols = '{:<65.64}{:<15.15}'
            console(cols.format('Title', 'Task'))
            console('-' * 80)
            for entry in get_entries(options.task):
                console(cols.format(entry.title, entry.task))


@event('options.register')
def register_options():
    parser = options.register_command('backlog', do_cli, help='view or clear entries from backlog plugin')
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')
    list_parser = subparsers.add_parser('list', help='list entries currently in backlog')
    list_parser.add_argument('task', nargs='?', help='if specified, only show entries for given task')
    clear_parser = subparsers.add_parser('clear', help='clear entries currently in backlog')
    clear_parser.add_argument('task', nargs='?', help='if specified, only clear entries for given task')
