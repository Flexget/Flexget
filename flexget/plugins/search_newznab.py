import logging
import urllib

import feedparser

from flexget import plugin, validator
from flexget.entry import Entry
from flexget.event import event
from flexget.plugins.api_tvrage import lookup_series

__author__ = 'deksan'

log = logging.getLogger('newznab')


class Newznab(object):
    """
    Newznab search plugin
    Provide a url or your website + apikey and a category

    Config example::

        newznab:
          url: "http://website/api?apikey=xxxxxxxxxxxxxxxxxxxxxxxxxx&t=movie&extended=1"
          website: https://website
          apikey: xxxxxxxxxxxxxxxxxxxxxxxxxx
          category: movie

    Category is any of: movie, tvsearch, music, book
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['movie', 'tvsearch', 'tv', 'music', 'book']},
            'url': {'type': 'string', 'format': 'url'},
            'website': {'type': 'string', 'format': 'url'},
            'apikey': {'type': 'string'}
        },
        'required': ['category'],
        'additionalProperties': False
    }

    def build_config(self, config):
        if config['category'] == 'tv':
            config['category'] = 'tvsearch'
        log.debug(config['category'])
        if 'url' not in config:
            if 'apikey' in config and 'website' in config:
                params = {
                    't': config['category'],
                    'apikey': config['apikey'],
                    'extended': 1
                }
                config['url'] = config['website'] + '/api?' + urllib.urlencode(params)
        return config

    def fill_entries_for_url(self, url, config):
        entries = []
        rss = feedparser.parse(url)
        status = rss.get('status', False)
        if status != 200 and status != 301:     # in cae of redirection...
            log.error('Search result not 200 (OK), received %s' % status)
            raise

        if not len(rss.entries):
            log.info('No results returned')

        for rss_entry in rss.entries:
            new_entry = Entry()
            for key in rss_entry.keys():
                new_entry[key] = rss_entry[key]
            new_entry['url'] = new_entry['link']
            if rss_entry.enclosures:
                size = int(rss_entry.enclosures[0]['length'])  # B
                new_entry['content_size'] = size / 2**20       # MB
            entries.append(new_entry)
        return entries

    def search(self, task, entry, config=None):
        config = self.build_config(config)
        if config['category'] == 'movie':
            return self.do_search_movie(entry, config)
        elif config['category'] == 'tvsearch':
            return self.do_search_tvsearch(entry, config)
        else:
            entries = []
            log.warning("Not done yet...")
            return entries

    def do_search_tvsearch(self, arg_entry, config=None):
        log.info('Searching for %s' % (arg_entry['title']))
        # normally this should be used with emit_series who has provided season and episodenumber
        if 'series_name' not in arg_entry or 'series_season' not in arg_entry or 'series_episode' not in arg_entry:
            return []
        if 'tvrage_id' not in arg_entry:
            serie_info = lookup_series(arg_entry['series_name'])
            if not serie_info:
                return []
            arg_entry['tvrage_id'] = serie_info.showid

        url = (config['url'] + '&rid=%s&season=%s&ep=%s' %
               (arg_entry['tvrage_id'], arg_entry['series_season'], arg_entry['series_episode']))
        return self.fill_entries_for_url(url, config)

    def do_search_movie(self, arg_entry, config=None):
        entries = []
        log.info('Searching for %s (imdbid:%s)' % (arg_entry['title'], arg_entry['imdb_id']))
        # normally this should be used with emit_movie_queue who has imdbid (i guess)
        if 'imdb_id' not in arg_entry:
            return entries

        imdb_id = arg_entry['imdb_id'].replace('tt', '')
        url = config['url'] + '&imdbid=' + imdb_id
        return self.fill_entries_for_url(url, config)


@event('plugin.register')
def register_plugin():
    plugin.register(Newznab, 'newznab', api_ver=2, groups=['search'])
