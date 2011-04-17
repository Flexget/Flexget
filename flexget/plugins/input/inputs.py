import logging
from flexget.plugin import register_plugin, get_plugins_by_phase, get_plugin_by_name, PluginError

log = logging.getLogger('inputs')


class PluginInputs(object):
    """ Allows the same input plugin to be configured multiple times in a feed.

    Example:
      inputs:
        - rss: http://feeda.com
        - rss: http://feedb.com
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        input_list = root.accept('list')
        # Get a list of apiv2 input plugins
        valid_inputs = [plugin for plugin in get_plugins_by_phase('input')
                        if plugin.api_ver > 1 and plugin.name != 'inputs']
        input_validator = input_list.accept('dict')
        # Build a dict validator that accepts the available input plugins and their settings
        for plugin in valid_inputs:
            if hasattr(plugin.instance, 'validator'):
                validator = plugin.instance.validator()
                if validator.name == 'root':
                    # If a root validator is returned, grab the list of child validators
                    input_validator.valid[plugin.name] = validator.valid
                else:
                    input_validator.valid[plugin.name] = [plugin.instance.validator()]
            else:
                input_validator.valid[plugin.name] = [validator.factory('any')]
        return root

    def on_feed_input(self, feed, config):
        entries = []
        entry_titles = set()
        entry_urls = set()
        for item in config:
            for input_name, input_config in item.iteritems():
                input = get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise PluginError('Plugin %s does not support API v2' % input_name)

                method = input.phase_handlers['on_feed_input']
                try:
                    result = method(feed, input_config)
                except PluginError, e:
                    log.warning('Error during input plugin %s: %s' % (input_name, e))
                    continue
                if not result:
                    log.warning('Input %s did not return anything' % input_name)
                    continue
                for entry in result:
                    if entry['title'] in entry_titles:
                        log.debug('Title `%s` already in entry list, skipping.' % entry['title'])
                        continue
                    if any(url in entry_urls for url in [entry.get('url')] + entry.get('urls', [])):
                        log.debug('URL for `%s` already in entry list, skipping.' % entry['title'])
                        continue
                    entries.append(entry)
                    entry_titles.add(entry['title'])
                    for url in [entry.get('url')] + entry.get('urls', []):
                        entry_urls.add(url)
        return entries


register_plugin(PluginInputs, 'inputs', api_ver=2)
