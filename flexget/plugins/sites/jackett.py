from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode, quote_plus
from past.utils import old_div

import logging
import feedparser

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.search import normalize_unicode

__author__ = 'davst'

log = logging.getLogger('jackett')


class Jackett(object):
    """
    Jackett search plugin
    Based on the newznab plugin
    Provide either url or website + apikey, and a category

    Config examples::

        jackett:
          host: https://website
          apikey: xxxxxxxxxxxxxxxxxxxxxxxxxx
          category: movie

        -- or --

        jackett:
          url:
            - "http://website/api?apikey=xxxxxxxxxxxxxxxxxxxxxxxxxx&t=movie&extended=1"
            - "http://website/api?apikey=xxxxxxxxxxxxxxxxxxxxxxxxxx&t=movie&extended=1"
          category: movie

    Category is any of: movie, tv, search (default)
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['movie', 'tv', 'search']},
            'url': one_or_more({'type': 'string', 'format': 'url'}),
            'host': {'type': 'string', 'format': 'url'},
            'api_key': {'type': 'string'}
        },
        'oneOf': [
            {'required': ['url']},
            {'required': ['host', 'api_key']}
        ],
        'additionalProperties': False
    }

    def build_config(self, config):
        config.setdefault('category', 'search')
        if 'url' not in config:
            params = {
                't': config['category'],
                'apikey': config['apikey'],
                'extended': 1
            }
            config['url'] = config['host'] + '/api?' + urlencode(params)
        if not isinstance(config['url'], list):
            config['url'] = [config['url']]
        return config

    def fill_entries_for_url(self, url, task):
        entries = []
        log.verbose('Fetching %s', url)

        try:
            r = task.requests.get(url)
        except task.requests.RequestException as e:
            raise PluginError("Failed fetching '%s': %s" % (url, e))

        rss = feedparser.parse(r.content)
        log.debug("Raw RSS: %s", rss)

        if not len(rss.entries):
            return []

        for rss_entry in rss.entries:
            new_entry = Entry()

            for key in list(rss_entry.keys()):
                new_entry[key] = rss_entry[key]
            new_entry['url'] = new_entry['link']
            if rss_entry.enclosures:
                size = int(rss_entry.enclosures[0]['length'])  # B
                new_entry['content_size'] = old_div(size, 2 ** 20)  # MB
            entries.append(new_entry)
        return entries

    def search(self, task, entry, config=None):
        config = self.build_config(config)
        if config['category'] == 'movie':
            return self.search_movie(entry, task, config)
        elif config['category'] == 'tv':
            return self.search_tv(entry, task, config)
        else:
            return self.search_generic(entry, task, config)

    def search_tv(self, arg_entry, task, config=None):
        entries = []
        log.verbose('Searching for %s', arg_entry['title'])
        # normally this should be used with next_series_episodes who has provided season and episodenumber
        if not all(value in arg_entry for value in ['series_name', 'series_episode', 'series_season']):
            return entries

        if arg_entry.get('tvrage_id'):
            lookup = '&rid=%s' % arg_entry.get('tvrage_id')
        else:
            lookup = '&q=%s' % quote_plus(arg_entry['series_name'])

        for url in config['url']:
            url = url + lookup + '&season=%s&ep=%s' % (arg_entry['series_season'], arg_entry['series_episode'])
            entries += self.fill_entries_for_url(url, task)
        return entries

    def search_movie(self, arg_entry, task, config=None):
        entries = []
        log.verbose('Searching for %s (imdbid:%s)', arg_entry['title'], arg_entry['imdb_id'])
        if 'imdb_id' not in arg_entry:
            log.debug('entry %s does not have `imdb_id` field present, skipping', arg_entry)
            return entries

        for url in config['url']:
            imdb_id = arg_entry['imdb_id'].replace('tt', '')
            url = url + '&imdbid=' + imdb_id
            entries += self.fill_entries_for_url(url, task)
        return entries

    def search_generic(self, arg_entry, task, config=None):
        entries = []
        log.verbose('Searching for %s by title', arg_entry['title'])
        query = normalize_unicode(arg_entry['title'])
        query = quote_plus(query.encode('utf8'))
        for url in config['url']:
            url = url + '&q=' + query
            entries += self.fill_entries_for_url(url, task)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Jackett, 'jackett', api_ver=2, groups=['search'])
