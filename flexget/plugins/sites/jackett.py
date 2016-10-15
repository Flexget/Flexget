from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.utils import old_div
from future.moves.urllib.parse import urlencode, quote_plus

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import normalize_unicode
import feedparser

__author__ = 'davst'

log = logging.getLogger('jackett')


class Jackett(object):
    """
    Jackett search plugin
    Based on the newznab plugin
    Provide either url or website + apikey, and a category

    Config examples::

        Jackett:
          website: https://website
          apikey: xxxxxxxxxxxxxxxxxxxxxxxxxx
          category: movie
          
        -- or --
        
        Jackett:
          url: "http://website/api?apikey=xxxxxxxxxxxxxxxxxxxxxxxxxx&t=movie&extended=1"
          category: movie

    Category is any of: movie, tv, search (default)
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['movie',  'tv', 'search']},
            'url': {'type': 'string', 'format': 'url'},
            'website': {'type': 'string', 'format': 'url'},
            'apikey': {'type': 'string'}
        },
        'oneOf': [
            {'required': ['url']},
            {'required': ['website', 'apikey']}
        ],
        'additionalProperties': False
    }

    def build_config(self, config):
        log.debug(type(config))

        if 'url' not in config:
            if 'apikey' in config and 'website' in config:
                params = {
                    't': config['category'],
                    'apikey': config['apikey'],
                    'extended': 1
                }
                config['url'] = config['website'] + '/api?' + urlencode(params)

        return config

    def fill_entries_for_url(self, url, task):
        entries = []
        log.verbose('Fetching %s', url)

        try:
            r = task.requests.get(url)
        except task.requests.RequestException as e:
            raise PluginError("Failed fetching '%s': %s" % (url, e))

        rss = feedparser.parse(r.content)
        log.debug("Raw RSS: %s" % rss)

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
            return self.do_search_movie(entry, task, config)
        elif config['category'] == 'tv':
            return self.do_search_tvsearch(entry, task, config)
        else:
            return self.do_search_search(entry, task, config)

    def do_search_tvsearch(self, arg_entry, task, config=None):
        log.info('Searching for %s' % (arg_entry['title']))
        # normally this should be used with next_series_episodes who has provided season and episodenumber
        if not all(value in arg_entry for value in ['series_name', 'series_episode', 'series_season']):
            return []
        if arg_entry.get('tvrage_id'):
            lookup = '&rid=%s' % arg_entry.get('tvrage_id')
        else:
            lookup = '&q=%s' % quote_plus(arg_entry['series_name'])
        url = config['url'] + lookup + '&season=%s&ep=%s' % (arg_entry['series_season'], arg_entry['series_episode'])
        return self.fill_entries_for_url(url, task)

    def do_search_movie(self, arg_entry, task, config=None):
        entries = []
        log.info('Searching for %s (imdbid:%s)' % (arg_entry['title'], arg_entry['imdb_id']))
        # normally this should be used with emit_movie_queue who has imdbid (i guess)
        if 'imdb_id' not in arg_entry:
            return []

        imdb_id = arg_entry['imdb_id'].replace('tt', '')
        url = config['url'] + '&imdbid=' + imdb_id
        return self.fill_entries_for_url(url, task)

    def do_search_search(self, arg_entry, task, config=None):
        entries = []
        log.info('Searching for %s by title' % (arg_entry['title']))
        # general search by matching title
        if 'title' not in arg_entry:
            return []
        query = normalize_unicode(arg_entry['title'])
        query = quote_plus(query.encode('utf8'))
        url = config['url'] + '&q=' + query
        return self.fill_entries_for_url(url, task)

@event('plugin.register')
def register_plugin():
    plugin.register(Jackett, 'jackett', api_ver=2, groups=['search'])
