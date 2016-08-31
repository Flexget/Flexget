from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.utils import old_div
from future.moves.urllib.parse import urlencode, quote

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
import feedparser

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
        log.debug(type(config))

        if config['category'] == 'tv':
            config['category'] = 'tvsearch'

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
        log.verbose('Fetching %s' % url)

        try:
            r = task.requests.get(url)
        except task.requests.RequestException as e:
            log.error("Failed fetching '%s': %s" % (url, e))

        rss = feedparser.parse(r.content)
        log.debug("Raw RSS: %s" % rss)

        if not len(rss.entries):
            log.info('No results returned')

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
        elif config['category'] == 'tvsearch':
            return self.do_search_tvsearch(entry, task, config)
        else:
            entries = []
            log.warning("Not done yet...")
            return entries

    def do_search_tvsearch(self, arg_entry, task, config=None):
        log.info('Searching for %s' % (arg_entry['title']))
        # normally this should be used with next_series_episodes who has provided season and episodenumber
        if 'series_name' not in arg_entry or 'series_season' not in arg_entry or 'series_episode' not in arg_entry:
            return []
        if arg_entry.get('tvrage_id'):
            lookup = '&rid=%s' % arg_entry.get('tvrage_id')
        else:
            lookup = '&q=%s' % quote(arg_entry['series_name'])
        url = config['url'] + lookup + '&season=%s&ep=%s' % (arg_entry['series_season'], arg_entry['series_episode'])
        return self.fill_entries_for_url(url, task)

    def do_search_movie(self, arg_entry, task, config=None):
        entries = []
        log.info('Searching for %s (imdbid:%s)' % (arg_entry['title'], arg_entry['imdb_id']))
        # normally this should be used with emit_movie_queue who has imdbid (i guess)
        if 'imdb_id' not in arg_entry:
            return entries

        imdb_id = arg_entry['imdb_id'].replace('tt', '')
        url = config['url'] + '&imdbid=' + imdb_id
        return self.fill_entries_for_url(url, task)


@event('plugin.register')
def register_plugin():
    plugin.register(Newznab, 'newznab', api_ver=2, groups=['search'])
