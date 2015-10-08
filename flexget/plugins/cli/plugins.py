from __future__ import unicode_literals, division, absolute_import, print_function
import logging

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.plugin import get_plugins

log = logging.getLogger('plugins')


@event('manager.subcommand.plugins')
def plugins_summary(manager, options):
    if options.porcelain:
        console('%-30s%-s%-30s%-s%s' % ('Name', '|', 'Roles (priority)', '|', 'Info'))
    else:
        console('-' * 79)
        console('%-30s%-30s%-s' % ('Name', 'Roles (priority)', 'Info'))
        console('-' * 79)

    # print the list
    for plugin in sorted(get_plugins(phase=options.phase, group=options.group)):
        # do not include test classes, unless in debug mode
        if plugin.get('debug_plugin', False) and not options.debug:
            continue
        flags = []
        if plugin.instance.__doc__:
            flags.append('--doc')
        if plugin.builtin:
            flags.append('builtin')
        if plugin.debug:
            flags.append('debug')
        handlers = plugin.phase_handlers
        roles = ', '.join('%s(%s)' % (phase, handlers[phase].priority) for phase in handlers)
        tab = '|'
        if options.porcelain:
            console('%-30s%-s%-30s%-s%s' % (plugin.name, '|', roles, '|', ', '.join(flags)))
        else:
            console('%-30s%-30s%-s' % (plugin.name, roles, ', '.join(flags)))
    if options.porcelain:
        pass
    else:
        console('-' * 79)


@event('options.register')
def register_parser_arguments():
    plugins_subparser = options.register_command('plugins', plugins_summary, help='print registered plugin summaries')
    plugins_subparser.add_argument('--group', help='show plugins belonging to this group')
    plugins_subparser.add_argument('--phase', help='show plugins that act on this phase')
    plugins_subparser.add_argument('--porcelain', action='store_true', help='make the output parseable')
