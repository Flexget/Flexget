from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging


from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.plugin import get_plugins
from flexget.terminal import CLITable, CLITableError, table_parser

log = logging.getLogger('plugins')


def plugins_summary(manager, options):
    header = ['Keyword', 'Phases', 'Flags']
    table_data = [header]
    for plugin in sorted(get_plugins(phase=options.phase, group=options.group)):
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
            prio = handlers[phase].priority
            roles.append('{0}({1})'.format(phase, prio))

        if options.table_type == 'porcelain':
            jc = ', '
        else:
            jc = '\n'

        table_data.append([plugin.name, jc.join(roles), jc.join(flags)])

    table = CLITable(options.table_type, table_data)
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('plugins', plugins_summary, help='Print registered plugin summaries', 
                                      parents=[table_parser])
    parser.add_argument('--group', help='Show plugins belonging to this group')
    parser.add_argument('--phase', help='Show plugins that act on this phase')
