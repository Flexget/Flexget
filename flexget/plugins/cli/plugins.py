from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.options import add_subparser
from flexget.plugin import plugins

log = logging.getLogger('plugins')


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

parser = add_subparser('plugins', plugins_summary, help='print registered plugin summaries')
