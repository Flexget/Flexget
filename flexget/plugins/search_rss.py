from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
from flexget.task import Task
from flexget.plugin import register_plugin, get_plugin_by_name

log = logging.getLogger('search_rss')


class SearchRSS(object):
    """A generic search plugin that can use rss based search feeds. Configure it like rss
    plugin, but include {{{search_term}}} in the url where the search term should go."""

    schema = {'$ref': '/schema/plugin/rss'}

    def search(self, query, comparator, config=None):
        from flexget.utils.template import environment
        from flexget.manager import manager
        comparator.set_seq1(query)
        search_string = urllib.quote(comparator.search_string().encode('utf-8'))
        rss_plugin = get_plugin_by_name('rss')
        # Create a fake task to pass to the rss plugin input handler
        task = Task(manager, 'search_rss_task', {})
        # Use a copy of the config, so we don't overwrite jinja url when filling in search term
        config = rss_plugin.instance.build_config(config).copy()
        template = environment.from_string(config['url'])
        config['url'] = template.render({'search_term': search_string})
        config['all_entries'] = True
        # TODO: capture some other_fields to try to find seed/peer/content_size numbers?
        entries = []
        for entry in rss_plugin.phase_handlers['input'](task, config):
            if comparator.matches(entry['title']):
                entry['search_ratio'] = comparator.ratio()
                entries.append(entry)
        return entries

register_plugin(SearchRSS, 'search_rss', groups=['search'])
