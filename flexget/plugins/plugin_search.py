import logging
from flexget.plugin import get_plugins_by_group, PluginWarning, PluginError, \
    register_parser_option, register_plugin, get_plugin_by_name

log = logging.getLogger('search')


class SearchPlugins(object):

    """
        Implements --search-plugins
    """

    def on_process_start(self, feed):
        if feed.manager.options.search_plugins:
            feed.manager.disable_feeds()
            header = '-- Supported search plugins: '
            header = header + '-' * (79 - len(header))
            print header
            for plugin in get_plugins_by_group('search'):
                print ' %s' % plugin.name
            print '-' * 79


class PluginSearch(object):
    """
        Search entry from sites. Accepts list of known search plugins, list is in priority order.
        Once hit has been found no more searches are performed. Should be used only when
        there is no other way to get working download url, ie. when input plugin does not provide
        any downloadable urls.

        Example:

        search:
          - newtorrents
          - piratebay

        Notes:
        - Some url rewriters will use search plugins automatically if enry url points into a search page.
    """

    def validator(self):
        from flexget import validator
        search = validator.factory('list')
        plugins = {}
        names = []
        for plugin in get_plugins_by_group('search'):
            # If the plugin has a validator, get it's validator and make it a
            # child of the search plugins
            if not hasattr(plugin.instance, 'validator'):
                # Create choice validator for plugins without validators later
                names.append(plugin.name)
            else:
                plugin_validator = plugin.instance.validator()
                if isinstance(plugin_validator, validator.Validator):
                    search.accept('dict').accept(plugin_validator, key=plugin.name)
                else:
                    log.error("plugin %s has a validator method, but does not "
                              "return a validator instance when called with "
                              "search plugin." % plugin.name)
        search.accept('choice').accept_choices(names)
        return search

    def on_feed_urlrewrite(self, feed):
        # no searches in unit test mode
        if feed.manager.unit_test:
            return

        plugins = {}
        for plugin in get_plugins_by_group('search'):
            plugins[plugin.name] = plugin.instance

        # search accepted and imaginary entries
        for entry in feed.accepted + [e for e in feed.entries if e.get('imaginary')]:
            found = False
            # loop through configured searches
            search_plugins = feed.config.get('search', [])
            for name in search_plugins:
                config = None
                if isinstance(name, dict):
                    # assume the name is the first/only key in the dict.
                    name, config = name.items()[0]
                log.verbose('Searching `%s` from %s' % (entry['title'], name))
                try:
                    results = plugins[name].search(entry['title'], config, exact=True)
                    if results:
                        url = results[0]['url']
                        log.debug('Found url: %s' % url)
                        entry['url'] = url
                        found = True
                        break
                except (PluginError, PluginWarning), pw:
                    log.verbose('Failed: %s' % pw.value)
                    continue

            # Search failed
            if not found:
                # If I don't have a URL, doesn't matter if I'm immortal...
                entry['immortal'] = False
                feed.reject(entry, 'search failed')
            else:
                # Populate quality
                # TODO: why does search plugin invoke quality here?
                get_plugin_by_name('metainfo_quality').instance.get_quality(entry)

register_plugin(PluginSearch, 'search')
register_plugin(SearchPlugins, '--search-plugins', builtin=True)
register_parser_option('--search-plugins', action='store_true', dest='search_plugins', default=False,
                       help='List supported search plugins.')
