from sqlalchemy import desc

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, console, table_parser

from . import db


def do_cli(manager, options):
    with Session() as session:
        query = session.query(db.History)
        if options.search:
            search_term = options.search.replace(' ', '%').replace('.', '%')
            query = query.filter(db.History.title.like('%' + search_term + '%'))
        if options.task:
            query = query.filter(db.History.task.like('%' + options.task + '%'))
        query = query.order_by(desc(db.History.time)).limit(options.limit)
        if options.short:
            headers = ['Time', 'Title']
        else:
            headers = ['Field', 'Value']
        title = 'Showing {} entries from History'.format(query.count())
        table = TerminalTable(*headers, table_type=options.table_type, title=title)
        for item in reversed(query.all()):
            if not options.short:
                table.add_row('Task', item.task)
                table.add_row('Title', item.title)
                table.add_row('URL', item.url)
                table.add_row('Time', item.time.strftime("%c"))
                table.add_row('Details', item.details)
                if item.filename:
                    table.add_row('Stored', item.filename)
                table.rows[-1].end_section = True
            else:
                table.add_row(item.time.strftime("%c"), item.title)
    if not table.row_count:
        console('No history to display')
        return
    console(table)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'history',
        do_cli,
        help='View the history of entries that FlexGet has accepted',
        parents=[table_parser],
    )
    parser.add_argument(
        '--limit',
        action='store',
        type=int,
        metavar='NUM',
        default=50,
        help='limit to %(metavar)s results',
    )
    parser.add_argument(
        '--search',
        action='store',
        metavar='TERM',
        help='Limit to results that contain %(metavar)s',
    )
    parser.add_argument(
        '--task', action='store', metavar='TASK', help='Limit to results in specified %(metavar)s'
    )
    parser.add_argument(
        '--short', '-s', action='store_true', dest='short', default=False, help='Shorter output'
    )
