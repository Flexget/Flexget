from __future__ import unicode_literals, division, absolute_import
import logging
from argparse import SUPPRESS
from flexget.plugin import register_parser_option, plugins
from flexget.event import event

log = logging.getLogger('plugins')


@event('manager.startup')
def plugins_summary(manager):
    if manager.options.plugins:
        manager.disable_tasks()
        print '-' * 79
        print '%-20s%-30s%s' % ('Name', 'Roles (priority)', 'Info')
        print '-' * 79

        # print the list
        for name in sorted(plugins):
            plugin = plugins[name]
            # do not include test classes, unless in debug mode
            if plugin.get('debug_plugin', False) and not manager.options.debug:
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

register_parser_option('--plugins', action='store_true', dest='plugins', default=False,
                       help='Print registered plugins summary')
register_parser_option('--list', action='store_true', dest='plugins', default=False,
                       help=SUPPRESS)
