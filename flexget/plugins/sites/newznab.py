from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.utils import old_div
from future.moves.urllib.parse import urlencode, quote

import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import RequestException

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

    Category is one of: movie, tv
    """

    schema = {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['movie', 'tv']},
            'url': {'type': 'string', 'format': 'url'},
            'website': {'type': 'string', 'format': 'url'},
            'apikey': {'type': 'string'}
        },
        'required': ['category'],
        'additionalProperties': False
    }

    def build_config(self, config):
        if 'url' not in config:
            if 'apikey' in config and 'website' in config:
                category = config['category']
                params = {
                    't': 'tvsearch' if category == 'tv' else category,
                    'apikey': config['apikey'],
                    'extended': 1
                }
                config['url'] = config['website'] + '/api?' + urlencode(params)
        return config

    def fill_entries_for_url(self, url, task):
        entries = []
        try:
            response = task.requests.get(url)
        except RequestException as e:
            log.error("Failed fetching '%s': %s", url, e)
            return entries

        rss = feedparser.parse(response.content)
        log.debug("Raw RSS: %s", rss)

        if not len(rss.entries):
            log.info('No results returned')

        for rss_entry in rss.entries:
            new_entry = Entry()
            for key in rss_entry.keys():
                new_entry[key] = rss_entry[key]
            new_entry['url'] = new_entry['link']
            if rss_entry.enclosures:
                size = int(rss_entry.enclosures[0]['length'])  # B
                new_entry['content_size'] = old_div(size, 2 ** 20)  # MB
            entries.append(new_entry)
        return entries

    def search(self, task, entry, config=None):
        log.info('Searching for %s', entry['title'])
        config = self.build_config(config)
        category = config['category']
        url = ''

        if category == 'movie':
            if 'imdb_id' not in entry:
                log.error('Missing `imdb_id`')
                return
            url = config['url'] + '&imdbid=' + entry['imdb_id'].replace('tt', '')

        elif category == 'tv':
            if 'series_name' not in entry:
                log.error('Missing `series_name`')
                return

            lookup = ''
            if 'tvdb_id' in entry:
                lookup += '&tvdbid=%s' % entry['tvdb_id']
            else:
                lookup += '&q=%s' % quote(entry['series_name'])
                if 'series_season' in entry:
                    lookup += '&season=%s' % entry['series_season']
                if 'series_episode' in entry:
                    lookup += '&ep=%s' % entry['series_episode']
            url = config['url'] + lookup

        return self.fill_entries_for_url(url, task)


@event('plugin.register')
def register_plugin():
    plugin.register(Newznab, 'newznab', api_ver=2, interfaces=['search'])
