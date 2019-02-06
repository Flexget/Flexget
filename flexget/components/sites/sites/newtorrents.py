from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup
from flexget.components.sites.utils import torrent_availability, normalize_unicode
from flexget.utils import requests

log = logging.getLogger('newtorrents')


class NewTorrents(object):
    """NewTorrents urlrewriter and search plugin."""

    def __init__(self):
        self.resolved = []

    # UrlRewriter plugin API
    def url_rewritable(self, task, entry):
        # Return true only for urls that can and should be resolved
        if entry['url'].startswith('http://www.newtorrents.info/down.php?'):
            return False
        return (
            entry['url'].startswith('http://www.newtorrents.info')
            and not entry['url'] in self.resolved
        )

    # UrlRewriter plugin API
    def url_rewrite(self, task, entry):
        url = entry['url']
        if url.startswith('http://www.newtorrents.info/?q=') or url.startswith(
            'http://www.newtorrents.info/search'
        ):
            results = self.entries_from_search(entry['title'], url=url)
            if not results:
                raise UrlRewritingError("No matches for %s" % entry['title'])
            url = results[0]['url']
        else:
            url = self.url_from_page(url)

        if url:
            entry['url'] = url
            self.resolved.append(url)
        else:
            raise UrlRewritingError('Bug in newtorrents urlrewriter')

    # Search plugin API
    def search(self, task, entry, config=None):
        entries = set()
        for search_string in entry.get('search_string', [entry['title']]):
            entries.update(self.entries_from_search(search_string))
        return entries

    @plugin.internet(log)
    def url_from_page(self, url):
        """Parses torrent url from newtorrents download page"""
        try:
            page = requests.get(url)
            data = page.text
        except requests.RequestException:
            raise UrlRewritingError('URLerror when retrieving page')
        p = re.compile(r"copy\(\'(.*)\'\)", re.IGNORECASE)
        f = p.search(data)
        if not f:
            # the link in which plugin relies is missing!
            raise UrlRewritingError(
                'Failed to get url from download page. Plugin may need a update.'
            )
        else:
            return f.group(1)

    @plugin.internet(log)
    def entries_from_search(self, name, url=None):
        """Parses torrent download url from search results"""
        name = normalize_unicode(name)
        if not url:
            url = 'http://www.newtorrents.info/search/%s' % quote(
                name.encode('utf-8'), safe=b':/~?=&%'
            )

        log.debug('search url: %s' % url)

        html = requests.get(url).text
        # fix </SCR'+'IPT> so that BS does not crash
        # TODO: should use beautifulsoup massage
        html = re.sub(r'(</SCR.*?)...(.*?IPT>)', r'\1\2', html)

        soup = get_soup(html)
        # saving torrents in dict
        torrents = []
        for link in soup.find_all('a', attrs={'href': re.compile('down.php')}):
            torrent_url = 'http://www.newtorrents.info%s' % link.get('href')
            release_name = link.parent.next.get('title')
            # quick dirty hack
            seed = link.find_next('td', attrs={'class': re.compile('s')}).renderContents()
            if seed == 'n/a':
                seed = 0
            else:
                try:
                    seed = int(seed)
                except ValueError:
                    log.warning(
                        'Error converting seed value (%s) from newtorrents to integer.' % seed
                    )
                    seed = 0

            # TODO: also parse content_size and peers from results
            torrents.append(
                Entry(
                    title=release_name,
                    url=torrent_url,
                    torrent_seeds=seed,
                    torrent_availability=torrent_availability(seed, 0),
                )
            )
        # sort with seed number Reverse order
        torrents.sort(reverse=True, key=lambda x: x.get('torrent_availability', 0))
        # choose the torrent
        if not torrents:
            dashindex = name.rfind('-')
            if dashindex != -1:
                return self.entries_from_search(name[:dashindex])
            else:
                return torrents
        else:
            if len(torrents) == 1:
                log.debug('found only one matching search result.')
            else:
                log.debug(
                    'search result contains multiple matches, sorted %s by most seeders' % torrents
                )
            return torrents


@event('plugin.register')
def register_plugin():
    plugin.register(NewTorrents, 'newtorrents', interfaces=['urlrewriter', 'search'], api_ver=2)
