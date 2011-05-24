import logging
from optparse import SUPPRESS_HELP
from flexget.plugin import register_plugin, register_parser_option, plugins

log = logging.getLogger('plugins')


class PluginsList(object):
    """
        Implements --plugins
    """

    def on_process_start(self, feed):
        if feed.manager.options.plugins:
            feed.manager.disable_feeds()
            self.plugins_summary(feed.manager.options)

    def plugins_summary(self, options):
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

register_plugin(PluginsList, '--plugins', builtin=True)
register_parser_option('--plugins', action='store_true', dest='plugins', default=False,
                       help='Print registered plugins summary')
register_parser_option('--list', action='store_true', dest='plugins', default=False,
                       help=SUPPRESS_HELP)
