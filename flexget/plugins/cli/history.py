from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from sqlalchemy import desc

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.logger import console
from flexget.terminal import TerminalTable, CLITableError, table_parser
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
        for item in reversed(query.all()):
            titles = 'Task\nTitle\nURL\nTime\nDetails'
            data = '{}\n{}\n{}\n{}\n{}'.format(item.task, item.title, item.url, item.time.strftime("%c"), item.details)
            if item.filename:
                titles += '\nStored'
                data = '{}\n{}\n{}\n{}\n{}\n{}'.format(item.task, item.title, item.url, item.time.strftime("%c"),
                                                       item.details, item.filename)
            table_data.append([titles, data])

    title = 'Showing {} entries from History'.format(query.count())
    table = TerminalTable(options.table_type, table_data, title=title, check_size=options.check_size)
    table.table.inner_row_border = True

    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('history', do_cli, help='view the history of entries that FlexGet has accepted',
                                      parents=[table_parser])
    parser.add_argument('--limit', action='store', type=int, metavar='NUM', default=50,
                        help='limit to %(metavar)s results')
    parser.add_argument('--search', action='store', metavar='TERM', help='limit to results that contain %(metavar)s')
    parser.add_argument('--task', action='store', metavar='TASK', help='limit to results in specified %(metavar)s')
