from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget.config_schema import one_or_more
from flexget.manager import Session
from flexget.plugins.internal.api_t411 import T411Proxy, FriendlySearchQuery, ApiError
from flexget import plugin
from flexget.event import event

log = logging.getLogger('t411_plugin')


def escape_query(search_strings):
    """
    Escaping some expression Grey's -> Grey's + Greys + Grey, Marvel's ->Marvel's + Marvels + Marvel etc
    :param query str[]:
    :return:
    """
    result = []
    for search_string in search_strings:
        result.append(search_string)
        short_query = re.sub("'", "", search_string)
        if search_string != short_query:
            result.append(short_query)
            very_short_query = re.sub("'[a-z]", "", search_string)
            if short_query != very_short_query:
                result.append(very_short_query)
    return result


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
        query.term_names = list(config.get('terms', []))
        query.max_results = config.get('max_results')
        return query

    @plugin.internet(log)
    def on_task_input(self, task, config):
        proxy = T411Proxy()
        proxy.set_credential()
        query = T411InputPlugin.build_request_from(config)
        try:
            return proxy.search(query)
        except ApiError as e:
            log.warning("Server send an error message : %d - %s", e.code, e.message)
            return []

    @classmethod
    @plugin.internet(log)
    def search(cls, entry=None, config=None, task=None):
        proxy = T411Proxy()
        proxy.set_credential()

        query = T411InputPlugin.build_request_from(config)
        if entry.get('series_season'):
            query.add_season_term(entry['series_season'])
            query.add_episode_term(entry['series_episode'])
            search_strings = escape_query([entry['series_name']])
        else:
            search_strings = entry.get('search_strings', [entry['title']])
            search_strings = escape_query(search_strings)

        produced_entries = set()
        for search_string in search_strings:
            query.expression = search_string
            try:
                search_result = proxy.search(query)
                produced_entries.update(search_result)
            except ApiError as e:
                log.warning("Server send an error message : %d - %s", e.code, e.message)

        return produced_entries


class T411LookupPlugin(object):
    schema = {'type': 'string', 'enum': ['fill', 'override']}

    @staticmethod
    def lazy_lookup(entry):
        string_torrent_id = entry.get('t411_torrent_id')
        if string_torrent_id is None:
            log.warning('Looking up T411 for entry pass, no t411_torrent_id found.')

        torrent_id = int(string_torrent_id)
        proxy = T411Proxy()
        proxy.set_credential()
        with Session() as session:
            try:
                log.info("Lookup torrent details for %d", torrent_id)
                bind_details = proxy.details(torrent_id, session=session)
                unbind_details = [dict([
                    ('term_type_name', term.type.name),
                    ('term_type_id', term.type.id),
                    ('term_id', term.id),
                    ('term_name', term.name)]) for term in bind_details.terms]
                entry['t411_terms'] = unbind_details
            except ApiError as e:
                log.warning("Server send an error message : %d - %s", e.code, e.message)

    # Run after series and metainfo series
    @plugin.priority(110)
    def on_task_metainfo(self, task, config):
        proxy = T411Proxy()
        proxy.set_credential()
        for entry in task.entries:
            if entry.get('t411_torrent_id') is None:
                continue

            # entry.register_lazy_func(T411LookupPlugin.lazy_lookup, T411LookupPlugin.torrent_details_map)
            T411LookupPlugin.lazy_lookup(entry)
            if entry.get('t411_terms', eval_lazy=True) is not None:
                video_quality = proxy.parse_terms_to_quality(entry.get('t411_terms'))
                entry_quality = entry.get('quality')
                if video_quality is None:
                    log.info('Torrent %i hasn\'t video quality description, pass.', entry.get('t411_torrent_id'))
                    continue
                if entry_quality.source.name == 'unknown' or config == 'override':
                    entry_quality.source = video_quality.source
                if entry_quality.resolution.name == 'unknown' or config == 'override':
                    entry_quality.resolution = video_quality.resolution


@event('plugin.register')
def register_plugin():
    plugin.register(T411InputPlugin, 't411', groups=['search', 'input'], api_ver=2)
    plugin.register(T411LookupPlugin, 't411_lookup', api_ver=2)
