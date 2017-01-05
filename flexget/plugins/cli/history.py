from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from sqlalchemy import desc

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console
from flexget.plugins.output.history import History


def do_cli(manager, options):
    with Session() as session:
        query = session.query(History)
        if options.search:
            search_term = options.search.replace(' ', '%').replace('.', '%')
            query = query.filter(History.title.like('%' + search_term + '%'))
        if options.task:
            query = query.filter(History.task.like('%' + options.task + '%'))
        query = query.order_by(desc(History.time)).limit(options.limit)
        table_data = []
        if options.short:
            table_data.append(['Time', 'Title'])
        for item in reversed(query.all()):
            if not options.short:
                table_data.append(['Task', item.task])
                table_data.append(['Title', item.title])
                table_data.append(['URL', item.url])
                table_data.append(['Time', item.time.strftime("%c")])
                table_data.append(['Details', item.details])
                if item.filename:
                    table_data.append(['Stored', item.filename])
                if options.table_type != 'porcelain':
                    table_data.append([''])
            else:
                table_data.append([item.time.strftime("%c"), item.title])
    if not table_data:
        console('No history to display')
        return
    title = 'Showing {} entries from History'.format(query.count())
    if options.table_type != 'porcelain' and not options.short:
        del table_data[-1]

    try:
        table = TerminalTable(options.table_type, table_data, title=title, wrap_columns=[1])
        if not options.short:
            table.table.inner_heading_row_border = False
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('history', do_cli, help='View the history of entries that FlexGet has accepted',
                                      parents=[table_parser])
    parser.add_argument('--limit', action='store', type=int, metavar='NUM', default=50,
                        help='limit to %(metavar)s results')
    parser.add_argument('--search', action='store', metavar='TERM', help='Limit to results that contain %(metavar)s')
    parser.add_argument('--task', action='store', metavar='TASK', help='Limit to results in specified %(metavar)s')
    parser.add_argument('--short', '-s', action='store_true', dest='short', default=False, help='Shorter output')
