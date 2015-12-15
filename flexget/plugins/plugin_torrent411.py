from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.config_schema import one_or_more
from flexget.plugins.api_t411 import T411Proxy, FriendlySearchQuery

from flexget import plugin
from flexget.event import event

log = logging.getLogger('t411_input')


class T411InputPlugin(object):
    """T411 search/Input plugin.
    Before any usage, please add your credential with
    "flexget t411 add-auth <username> <password>"

    t411:
      category: <see available categories on "flexget t411 list-cats">
      terms: <see available terms on "flexget t411 list-terms --category <category name>"
      max_resutls: XXX
    """

    def __init__(self):
        self.schema = {
            'type': 'object',
            'properties': {
                'category': {'type': 'string'},
                'terms': one_or_more({'type': 'string'}),
                'max_results': {'type': 'number', 'default': 100}
            },
            'additionalProperties': False
        }

    @staticmethod
    def build_request_from(config):
        """
        Build a query from plugin config dict
        :param config: dict
        :return:
        """
        query = FriendlySearchQuery()
        query.category_name = config.get('category')
        query.term_names = config.get('terms', [])
        query.max_results = config.get('max_results')
        return query

    @plugin.internet(log)
    def on_task_input(self, task, config):
        proxy = T411Proxy()
        proxy.set_credential()
        query = T411InputPlugin.build_request_from(config)
        return proxy.search(query)

    @classmethod
    @plugin.internet(log)
    def search(cls, task, entry, config=None):
        proxy = T411Proxy()
        proxy.set_credential()
        query = T411InputPlugin.build_request_from(config)

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query.expression = search_string
            search_result = proxy.search(query)
            entries.update(search_result)

        return entries


class T411LookupPlugin:
    schema = {'type': 'boolean'}

    torrent_details_map = {
        't411_terms': lambda details: [term.name for term in details.terms],
    }

    @staticmethod
    def lazy_lookup(entry):
        torrent_id = entry.get('t411_torrent_id')
        if torrent_id:
            log.debug('Lookup for %s' % entry['t411_torrent_id'])
        else:
            raise plugin.PluginError('looking up T411 for entry failed, no t411_torrent_id passed.')

        proxy = T411Proxy()
        proxy.set_credential()
        details = proxy.details(torrent_id)
        entry.update_using_map(T411LookupPlugin.torrent_details_map, details)

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        for entry in task.entries:
            if entry.get('t411_torrent_id') is None:
                continue

            entry.register_lazy_func(T411LookupPlugin.lazy_lookup, T411LookupPlugin.torrent_details_map)


@event('plugin.register')
def register_plugin():
    plugin.register(T411InputPlugin, 't411', groups=['search', 'input'], api_ver=2)
    plugin.register(T411LookupPlugin, 't411_lookup', api_ver=2)
