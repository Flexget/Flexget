import inspect

from flexget import options
from flexget.event import event
from flexget.terminal import TerminalTable, console, table_parser
from flexget.utils.template import get_filters


def do_cli(manager, options):
    header = ['Name', 'Description']
    table = TerminalTable(*header, table_type=options.table_type, show_lines=True)
    for filter_name, filter in get_filters().items():
        if options.name and not options.name in filter_name:
            continue
        filter_doc = inspect.getdoc(filter) or ''
        table.add_row(filter_name, filter_doc)
    console(table)


@event('options.register')
def register_parser_arguments():
    # Register subcommand
    parser = options.register_command(
        'jinja-filters',
        do_cli,
        help='View registered jinja2 filters and their description',
        parents=[table_parser],
    )
    parser.add_argument('--name', help='Filter results by filter name')
