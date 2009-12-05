import logging
from optparse import SUPPRESS_HELP
from flexget.plugin import register_plugin, register_parser_option, plugins, FEED_EVENTS, get_plugins_by_event

log = logging.getLogger('plugins')


class PluginsList:
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

        # build the list
        plugins = []
        roles = {}
        for event in FEED_EVENTS:
            event_plugins = get_plugins_by_event(event)
            for info in event_plugins:
                for plugin in plugins:
                    if plugin['name'] == info['name']:
                        break
                else:
                    plugins.append(info)

            # build roles list
            for info in event_plugins:
                priority = info.priorities.get(event, '?')
                if info['name'] in roles:
                    roles[info['name']].append('%s(%s)' % (event, priority))
                else:
                    roles[info['name']] = ['%s(%s)' % (event, priority)]

        # print the list
        for plugin in plugins:
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
            name = plugin['name']
            print '%-20s%-30s%s' % (name, ', '.join(roles[name]), ', '.join(flags))

        print '-' * 79

register_plugin(PluginsList, '--plugins', builtin=True)
register_parser_option('--plugins', action='store_true', dest='plugins', default=False,
                       help='Print registered plugins summary')
register_parser_option('--list', action='store_true', dest='plugins', default=False,
                       help=SUPPRESS_HELP)
