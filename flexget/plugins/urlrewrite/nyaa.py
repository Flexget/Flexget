from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging

import feedparser

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.search import normalize_unicode

log = logging.getLogger('nyaa')

# TODO: Other categories
CATEGORIES = {'all': '0_0',
              'anime': '1_0',
              'anime eng': '1_37',
              'anime non-eng': '1_38',
              'anime raw': '1_11'}
FILTERS = ['all', 'filter remakes', 'trusted only', 'a+ only']


class UrlRewriteNyaa(object):
    """Nyaa urlrewriter and search plugin."""

    def validator(self):
        from flexget import validator

        root = validator.factory()
        root.accept('choice').accept_choices(CATEGORIES)
        advanced = root.accept('dict')
        advanced.accept('choice', key='category').accept_choices(CATEGORIES)
        advanced.accept('choice', key='filter').accept_choices(FILTERS)
        return root

    def search(self, task, entry, config):
        if not isinstance(config, dict):
            config = {'category': config}
        config.setdefault('category', 'anime eng')
        config.setdefault('filter', 'all')
        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            name = normalize_unicode(search_string)
            url = 'http://www.nyaa.eu/?page=rss&cats=%s&filter=%s&term=%s' % (
                  CATEGORIES[config['category']], FILTERS.index(config['filter']), quote(name.encode('utf-8')))

            log.debug('requesting: %s' % url)
            rss = feedparser.parse(url)

            status = rss.get('status', False)
            if status != 200:
                log.debug('Search result not 200 (OK), received %s' % status)
            if status >= 400:
                continue

            ex = rss.get('bozo_exception', False)
            if ex:
                log.error('Got bozo_exception (bad feed) on %s' % url)
                continue

            for item in rss.entries:

                entry = Entry()
                entry['title'] = item.title
                entry['url'] = item.link
                # TODO: parse some shit
                # entry['torrent_seeds'] = int(item.seeds)
                # entry['torrent_leeches'] = int(item.leechs)
                # entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                # entry['content_size'] = int(item.size) / 1024 / 1024

                entries.add(entry)

        return entries

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.nyaa.eu/?page=torrentinfo&tid=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('torrentinfo', 'download')


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNyaa, 'nyaa', groups=['search', 'urlrewriter'], api_ver=2)
