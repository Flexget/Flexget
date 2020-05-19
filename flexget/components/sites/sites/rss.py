from urllib.parse import quote

from jinja2 import TemplateSyntaxError
from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_unicode
from flexget.event import event

logger = logger.bind(name='search_rss')


class SearchRSS:
    """A generic search plugin that can use rss based search feeds. Configure it like rss
    plugin, but include {{{search_term}}} in the url where the search term should go."""

    schema = {'$ref': '/schema/plugin/rss'}

    def search(self, task, entry, config=None):
        from flexget.utils.template import environment

        search_strings = [
            quote(normalize_unicode(s).encode('utf-8'))
            for s in entry.get('search_strings', [entry['title']])
        ]
        rss_plugin = plugin.get_plugin_by_name('rss')
        entries = set()
        rss_config = rss_plugin.instance.build_config(config)
        try:
            template = environment.from_string(rss_config['url'])
        except TemplateSyntaxError as e:
            raise plugin.PluginError('Invalid jinja template as rss url: %s' % e)
        rss_config['all_entries'] = True
        for search_string in search_strings:
            rss_config['url'] = template.render({'search_term': search_string})
            # TODO: capture some other_fields to try to find seed/peer/content_size numbers?
            try:
                results = rss_plugin.phase_handlers['input'](task, rss_config)
            except plugin.PluginError as e:
                logger.error('Error attempting to get rss for {}: {}', rss_config['url'], e)
            else:
                entries.update(results)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchRSS, 'search_rss', interfaces=['search'], api_ver=2)
