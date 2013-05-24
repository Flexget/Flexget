from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, get_plugin_by_name, PluginError

log = logging.getLogger('inputs')


class PluginInputs(object):
    """
    Allows the same input plugin to be configured multiple times in a task.

    Example::

      inputs:
        - rss: http://feeda.com
        - rss: http://feedb.com
    """

    schema = {
        'type': 'array',
        'items': {'allOf': [{'$ref': '/schema/plugins?phase=input'}, {'maxProperties': 1, 'minProperties': 1}]}
    }

    def on_task_input(self, task, config):
        entries = []
        entry_titles = set()
        entry_urls = set()
        for item in config:
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
                    msg = 'Input %s did not return anything' % input_name
                    if getattr(task, 'no_entries_ok', False):
                        log.verbose(msg)
                    else:
                        log.warning(msg)
                    continue
                for entry in result:
                    if entry['title'] in entry_titles:
                        log.debug('Title `%s` already in entry list, skipping.' % entry['title'])
                        continue
                    urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                    if any(url in entry_urls for url in urls):
                        log.debug('URL for `%s` already in entry list, skipping.' % entry['title'])
                        continue
                    entries.append(entry)
                    entry_titles.add(entry['title'])
                    entry_urls.update(urls)
        return entries


register_plugin(PluginInputs, 'inputs', api_ver=2)
