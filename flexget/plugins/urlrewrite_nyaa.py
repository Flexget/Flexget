from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

import feedparser

from flexget.entry import Entry
from flexget.plugin import register_plugin, PluginWarning
from flexget.utils.search import normalize_unicode

log = logging.getLogger('nyaa')

# TODO: Other categories
CATEGORIES = {'all': '0_0',
              'anime': '1_0'}
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

    def search(self, entry, config):
        if not isinstance(config, dict):
            config = {'category': config}
        config.setdefault('category', 'anime')
        config.setdefault('filter', 'all')
        name = normalize_unicode(entry['title'])
        url = 'http://www.nyaa.eu/?page=rss&cats=%s&filter=%s&term=%s' % (
              CATEGORIES[config['category']], FILTERS.index(config['filter']), urllib.quote(name.encode('utf-8')))

        log.debug('requesting: %s' % url)
        rss = feedparser.parse(url)
        entries = []

        status = rss.get('status', False)
        if status != 200:
            raise PluginWarning('Search result not 200 (OK), received %s' % status)

        ex = rss.get('bozo_exception', False)
        if ex:
            raise PluginWarning('Got bozo_exception (bad feed)')

        for item in rss.entries:

            entry = Entry()
            entry['title'] = item.title
            entry['url'] = item.link
            # TODO: parse some shit
            #entry['torrent_seeds'] = int(item.seeds)
            #entry['torrent_leeches'] = int(item.leechs)
            #entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
            #entry['content_size'] = int(item.size) / 1024 / 1024

            entries.append(entry)

        # choose torrent
        if not entries:
            raise PluginWarning('No matches for %s' % name, log, log_once=True)

        entries.sort(reverse=True, key=lambda x: x.get('search_sort'))
        return entries

    def url_rewritable(self, task, entry):
        return entry['url'].startswith('http://www.nyaa.eu/?page=torrentinfo&tid=')

    def url_rewrite(self, task, entry):
        entry['url'] = entry['url'].replace('torrentinfo', 'download')

register_plugin(UrlRewriteNyaa, 'nyaa', groups=['search', 'urlrewriter'])
