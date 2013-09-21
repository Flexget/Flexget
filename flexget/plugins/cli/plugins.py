from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.event import event
from flexget.plugin import plugins

log = logging.getLogger('plugins')


@event('manager.subcommand.plugins')
def plugins_summary(manager, options):
    print '-' * 79
    print '%-20s%-30s%s' % ('Name', 'Roles (priority)', 'Info')
    print '-' * 79

    # print the list
    for name in sorted(plugins):
        plugin = plugins[name]
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
        print '%-20s%-30s%s' % (name, roles, ', '.join(flags))

    print '-' * 79


@event('register_parser_arguments')
def register_parser_arguments(core_parser):
    core_parser.add_subparser('plugins', help='print registered plugin summaries')
