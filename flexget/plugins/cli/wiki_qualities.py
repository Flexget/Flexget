from flexget import options
from flexget.event import event
from flexget.terminal import console
from flexget.utils.qualities import all_components


def do_cli(manager, options):
    components_by_cat = {}
    for component in all_components():
        cat = components_by_cat.setdefault(component.type.title().replace('_', ' '), [])
        cat.append(component)
    header = list(components_by_cat.keys())
    row = []
    for cat in header:
        row.append("<br>".join(str(v) for v in components_by_cat[cat]))
    console("|" + "|".join(header) + "|")
    console("|" + "|".join("---" for h in header) + "|")
    console(
        "|"
        + "|".join(
            "<br>".join(str(comp) for comp in sorted(comps, reverse=True))
            for comps in components_by_cat.values()
        )
        + "|"
    )


@event('options.register')
def register_parser_arguments():
    # Register subcommand
    parser = options.register_command(
        'wiki-qualities',
        do_cli,
        # If we don't specify the help argument, this won't show up in --help, which is good because it's not for users
        # help='Generate the list of qualities for exporting to the wiki.',
    )
