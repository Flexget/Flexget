from __future__ import unicode_literals, division, absolute_import
from difflib import SequenceMatcher
import logging

from flexget.plugin import get_plugins_by_group, PluginWarning, PluginError, \
    register_parser_option, register_plugin, priority

log = logging.getLogger('urlrewrite_search')


class SearchPlugins(object):

    """
        Implements --search-plugins
    """

    def on_process_start(self, task):
        if task.manager.options.search_plugins:
            task.manager.disable_tasks()
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

    Example::

      urlrewrite_search:
        - newtorrents
        - piratebay

    .. note:: Some url rewriters will use search plugins automatically if entry url
              points into a search page.
    """

    def validator(self):
        from flexget import validator
        search = validator.factory('list')
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

    # Run before main urlrewriting
    @priority(130)
    def on_task_urlrewrite(self, task, config):
        # no searches in unit test mode
        if task.manager.unit_test:
            return

        plugins = {}
        for plugin in get_plugins_by_group('search'):
            plugins[plugin.name] = plugin.instance

        # search accepted
        for entry in task.accepted:
            # loop through configured searches
            for name in config:
                search_config = None
                if isinstance(name, dict):
                    # assume the name is the first/only key in the dict.
                    name, search_config = name.items()[0]
                log.verbose('Searching `%s` from %s' % (entry['title'], name))
                try:
                    results = plugins[name].search(entry, search_config)
                    matcher = SequenceMatcher(a=entry['title'])
                    for result in sorted(results, key=lambda e: e.get('search_sort'), reverse=True):
                        matcher.set_seq2(result['title'])
                        if matcher.ratio() > 0.9:
                            log.debug('Found url: %s', result['url'])
                            entry['url'] = result['url']
                            break
                    else:
                        continue
                    break
                except (PluginError, PluginWarning) as pw:
                    log.verbose('Failed: %s' % pw.value)
                    continue

            # Search failed
            else:
                # If I don't have a URL, doesn't matter if I'm immortal...
                entry['immortal'] = False
                entry.reject('search failed')

register_plugin(PluginSearch, 'urlrewrite_search', api_ver=2)
register_plugin(SearchPlugins, '--search-plugins', builtin=True)
register_parser_option('--search-plugins', action='store_true', dest='search_plugins', default=False,
                       help='List supported search plugins.')
