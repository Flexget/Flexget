from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.config_schema import one_or_more
from flexget.plugins.api_t411 import T411Proxy, FriendlySearchQuery, Category, TermType, Term
from flexget.utils.cached_input import cached

from flexget import plugin
from flexget.event import event

log = logging.getLogger('t411_input')


class T411InputPlugin(object):

    def __init__(self):
        # proxy = T411Proxy()
        category_constraint = {'type': 'string'}
        terms_contraints = {'type': 'string'}
        # if not proxy.has_cached_criterias():
        #     category_constraint['enum'] = proxy.all_category_names()
        #     terms_contraints['enum'] = proxy.all_term_names()
        # else:
        #     log.warning('T411Proxy has not cached category names and term names.'
        #                 'Your config may use unavailable names ; these names will be ignored and noticed.')

        self.schema = {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'password': {'type': 'string'},
                'category': category_constraint,
                'terms': one_or_more(terms_contraints),
                'max_results': {'type': 'number', 'default': 100}
                },
            'required': ['username', 'password'],
            'additionalProperties': False
        }

    @cached('t411')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        proxy = T411Proxy(username=config['username'], password=config['password'])
        query = FriendlySearchQuery()
        query.category_name = config.get('category')
        query.term_names = config.get('terms', [])
        query.max_results = config.get('max_results')
        return proxy.search(query)

@event('plugin.register')
def register_plugin():
    plugin.register(T411InputPlugin, 't411', api_ver=2)
