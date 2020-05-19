from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='inputs')


class PluginInputs:
    """
    Allows the same input plugin to be configured multiple times in a task.

    Example::

      inputs:
        - rss: http://feeda.com
        - rss: http://feedb.com
    """

    schema = {
        'type': 'array',
        'items': {
            'allOf': [
                {'$ref': '/schema/plugins?phase=input'},
                {
                    'maxProperties': 1,
                    'error_maxProperties': 'Plugin options within inputs plugin must be indented 2 more spaces than '
                    'the first letter of the plugin name.',
                    'minProperties': 1,
                },
            ]
        },
    }

    def on_task_input(self, task, config):
        entry_titles = set()
        entry_urls = set()
        for item in config:
            for input_name, input_config in item.items():
                input = plugin.get_plugin_by_name(input_name)
                method = input.phase_handlers['input']
                try:
                    result = method(task, input_config)
                except plugin.PluginError as e:
                    logger.warning('Error during input plugin {}: {}', input_name, e)
                    continue
                if not result:
                    msg = 'Input %s did not return anything' % input_name
                    if getattr(task, 'no_entries_ok', False):
                        logger.verbose(msg)
                    else:
                        logger.warning(msg)
                    continue
                for entry in result:
                    if entry['title'] in entry_titles:
                        logger.debug('Title `{}` already in entry list, skipping.', entry['title'])
                        continue
                    urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                    if any(url in entry_urls for url in urls):
                        logger.debug(
                            'URL for `{}` already in entry list, skipping.', entry['title']
                        )
                        continue
                    yield entry
                    entry_titles.add(entry['title'])
                    entry_urls.update(urls)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginInputs, 'inputs', api_ver=2)
