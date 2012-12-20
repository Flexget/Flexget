from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.utils.cached_input import cached
from flexget.utils.search import StringComparator, MovieComparator, AnyComparator, clean_title
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError, \
    get_plugins_by_group, get_plugins_by_phase, PluginWarning

log = logging.getLogger('discover')


class Discover(object):
    """
    Discover content based on other inputs material.

    Example::

      discover:
        what:
          - emit_series: yes
        from:
          - piratebay
    """

    def validator(self):
        from flexget import validator
        discover = validator.factory('dict')

        inputs = discover.accept('list', key='what', required=True).accept('dict')
        for plugin in get_plugins_by_phase('input'):
            if hasattr(plugin.instance, 'validator'):
                inputs.accept(plugin.instance.validator, key=plugin.name)

        searches = discover.accept('list', key='from', required=True)
        no_config = searches.accept('choice')
        for plugin in get_plugins_by_group('search'):
            if hasattr(plugin.instance, 'validator'):
                searches.accept('dict').accept(plugin.instance.validator, key=plugin.name)
            else:
                no_config.accept(plugin.name)

        discover.accept('integer', key='limit')
        discover.accept('choice', key='type').accept_choices(['any', 'normal', 'exact', 'movies'])
        return discover

    def execute_inputs(self, config, task):
        """
        :param config: Discover config
        :param task: Current task
        :return: List of pseudo entries created by inputs under `what` configuration
        """

        entries = []
        entry_titles = set()
        entry_urls = set()
        # run inputs
        for item in config['what']:
            for input_name, input_config in item.iteritems():
                input = get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise PluginError('Plugin %s does not support API v2' % input_name)
                method = input.phase_handlers['input']
                try:
                    result = method(task, input_config)
                except PluginError as e:
                    log.warning('Error during input plugin %s: %s' % (input_name, e))
                    continue
                if not result:
                    log.warning('Input %s did not return anything' % input_name)
                    continue

                for entry in result:
                    urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                    if any(url in entry_urls for url in urls):
                        log.debug('URL for `%s` already in entry list, skipping.' % entry['title'])
                        continue

                    if entry['title'] in entry_titles:
                        log.verbose('Ignored duplicate title `%s`' % entry['title']) # TODO: should combine?
                    else:
                        entries.append(entry)
                        entry_titles.add(entry['title'])
                        entry_urls.update(urls)
        return entries

    def execute_searches(self, config, entries):
        """
        :param config: Discover plugin config
        :param entries: List of pseudo entries to search
        :return: List of entries found from search engines listed under `from` configuration
        """

        result = []
        if config.get('type', 'normal') == 'normal':
            comparator = StringComparator(cutoff=0.7, cleaner=clean_title)
        elif config['type'] == 'exact':
            comparator = StringComparator(cutoff=0.9)
        elif config['type'] == 'any':
            comparator = AnyComparator()
        else:
            comparator = MovieComparator()
        for item in config['from']:
            if isinstance(item, dict):
                plugin_name, plugin_config = item.items()[0]
            else:
                plugin_name, plugin_config = item, None
            search = get_plugin_by_name(plugin_name).instance
            if not callable(getattr(search, 'search')):
                log.critical('Search plugin %s does not implement search method' % plugin_name)
            for entry in entries:
                try:
                    search_results = search.search(entry['title'], comparator, plugin_config)
                    log.debug('Discovered %s entries from %s' % (len(search_results), plugin_name))
                    result.extend(search_results[:config.get('limit')])
                except (PluginError, PluginWarning):
                    log.debug('No results from %s' % plugin_name)
        return sorted(result, reverse=True, key=lambda x: x.get('search_sort'))

    @cached('discover')
    def on_task_input(self, task, config):
        entries = self.execute_inputs(config, task)
        log.verbose('Discovering %i titles ...' % len(entries))
        if len(entries) > 500:
            log.critical('Looks like your inputs in discover configuration produced over 500 entries, please reduce the amount!')
        return self.execute_searches(config, entries)


register_plugin(Discover, 'discover', api_ver=2)
