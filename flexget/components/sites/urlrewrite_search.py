from difflib import SequenceMatcher

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='urlrewrite_search')


class PluginSearch:
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

    schema = {
        'type': 'array',
        'items': {
            'allOf': [
                {'$ref': '/schema/plugins?interface=search'},
                {'maxProperties': 1, 'minProperties': 1},
            ]
        },
    }

    # Run before main urlrewriting
    @plugin.priority(130)
    def on_task_urlrewrite(self, task, config):
        # no searches in unit test mode
        if task.manager.unit_test:
            return

        plugins = {}
        for p in plugin.get_plugins(interface='search'):
            plugins[p.name] = p.instance

        # search accepted
        for entry in task.accepted:
            # loop through configured searches
            for name in config:
                search_config = None
                if isinstance(name, dict):
                    # the name is the first/only key in the dict.
                    name, search_config = list(name.items())[0]
                logger.verbose('Searching `{}` from {}', entry['title'], name)
                try:
                    try:
                        results = plugins[name].search(
                            task=task, entry=entry, config=search_config
                        )
                    except TypeError:
                        # Old search api did not take task argument
                        logger.warning(
                            'Search plugin {} does not support latest search api.', name
                        )
                        results = plugins[name].search(entry, search_config)
                    matcher = SequenceMatcher(a=entry['title'])
                    for result in results:
                        matcher.set_seq2(result['title'])
                        if matcher.ratio() > 0.9:
                            logger.debug('Found url: {}', result['url'])
                            entry['url'] = result['url']
                            break
                        else:
                            logger.debug('Match {} is not close enough', result['title'])
                    else:
                        continue
                    break
                except (plugin.PluginError, plugin.PluginWarning) as pw:
                    logger.verbose('Failed: {}', pw.value)
                    continue

            # Search failed
            else:
                # If I don't have a URL, doesn't matter if I'm immortal...
                entry['immortal'] = False
                entry.reject('search failed')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSearch, 'urlrewrite_search', api_ver=2)
