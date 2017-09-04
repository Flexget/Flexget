from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import inspect

from flexget import options
from flexget.event import event
from flexget.utils.template import get_filters
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console


def do_cli(manager, options):
    header = ['Name', 'Description']
    table_data = [header]
    for filter_name, filter in get_filters():
        if options.name and not options.name in filter_name:
            continue
        filter_doc = inspect.getdoc(filter) or ''
        table_data.append([filter_name, filter_doc])
    try:
        table = TerminalTable(options.table_type, table_data)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))
    else:
        console(table.output)


@event('options.register')
def register_parser_arguments():
    # Register subcommand
    parser = options.register_command('jinja-filters', do_cli,
                                      help='View registered jinja2 filters and their description',
                                      parents=[table_parser])
    parser.add_argument('--name', help='Filter results by filter name')
