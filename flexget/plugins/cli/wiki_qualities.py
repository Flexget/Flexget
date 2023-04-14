from itertools import zip_longest

from flexget import options
from flexget.event import event
from flexget.terminal import TerminalTable, console
from flexget.utils.qualities import all_components


def do_cli(manager, options):
    components_by_cat = {}
    for component in all_components():
        cat = components_by_cat.setdefault(component.type.title().replace('_', ' '), [])
        cat.append(component)
    for cat_list in components_by_cat.values():
        cat_list.sort(reverse=True)
    header = list(components_by_cat.keys())
    table = TerminalTable(*header, table_type='github')
    for row in zip_longest(*components_by_cat.values(), fillvalue=""):
        table.add_row(*[str(i) for i in row])
    console(table)


@event('options.register')
def register_parser_arguments():
    # Register subcommand
    options.register_command(
        'wiki-qualities',
        do_cli,
        # If we don't specify the help argument, this won't show up in --help, which is good because it's not for users
        # help='Generate the list of qualities for exporting to the wiki.',
    )
