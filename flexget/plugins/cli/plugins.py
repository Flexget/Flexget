from loguru import logger

from flexget import options
from flexget.event import event
from flexget.plugin import get_plugins
from flexget.terminal import TerminalTable, colorize, console, disable_colors, table_parser

logger = logger.bind(name='plugins')


def plugins_summary(manager, options):
    if options.table_type == 'porcelain':
        disable_colors()
    header = ['Keyword', 'Interfaces', 'Phases', 'Flags']
    table = TerminalTable(*header, table_type=options.table_type)
    for plugin in sorted(get_plugins(phase=options.phase, interface=options.interface)):
        if options.builtins and not plugin.builtin:
            continue

        flags = []
        if plugin.instance.__doc__:
            flags.append('doc')
        if plugin.builtin:
            flags.append('builtin')
        if plugin.debug:
            if not options.debug:
                continue
            flags.append('developers')

        handlers = plugin.phase_handlers
        roles = []
        for phase in handlers:
            priority = handlers[phase].priority
            roles.append(f'{phase}({priority})')

        name = colorize('green', plugin.name) if 'builtin' in flags else plugin.name
        table.add_row(name, ', '.join(plugin.interfaces), ', '.join(roles), ', '.join(flags))

    table.caption = colorize('green', ' Built-in plugins')
    table.caption_justify = 'left'
    console(table)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'plugins',
        plugins_summary,
        help='Print registered plugin summaries',
        parents=[table_parser],
    )
    parser.add_argument('--interface', help='Show plugins belonging to this interface')
    parser.add_argument('--phase', help='Show plugins that act on this phase')
    parser.add_argument('--builtins', action='store_true', help='Show just builtin plugins')
