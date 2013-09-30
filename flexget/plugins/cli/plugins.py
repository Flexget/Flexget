from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.event import event
from flexget.plugin import get_plugins

log = logging.getLogger('plugins')


@event('manager.subcommand.plugins')
def plugins_summary(manager, options):
    print '-' * 79
    print '%-20s%-30s%s' % ('Name', 'Roles (priority)', 'Info')
    print '-' * 79

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
        print '%-20s%-30s%s' % (plugin.name, roles, ', '.join(flags))

    print '-' * 79


@event('register_parser_arguments')
def register_parser_arguments(core_parser):
    plugins_subparser = core_parser.add_subparser('plugins', help='print registered plugin summaries')
    plugins_subparser.add_argument('--group', help='show plugins belonging to this group')
    plugins_subparser.add_argument('--phase', help='show plugins that act on this phase')
