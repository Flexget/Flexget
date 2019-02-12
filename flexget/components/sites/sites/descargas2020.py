from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup
from flexget.utils import requests

from flexget.entry import Entry
from flexget.components.sites.utils import normalize_unicode

import unicodedata

log = logging.getLogger('descargas2020')

DESCARGAS2020_TORRENT_FORMAT = 'http://descargas2020.com/download/{:0>6}.torrent'
REWRITABLE_REGEX = re.compile(
    r'https?://(www.)?(descargas2020|tvsinpagar|tumejortorrent|torrentlocura|torrentrapid).com/'
)


class UrlRewriteDescargas2020(object):
    """Descargas2020 urlrewriter and search."""

    schema = {'type': 'boolean', 'default': False}

    def __init__(self):
        self._session = None

    @property
    def session(self):
        # TODO: This is not used for all requests even ..
        if self._session is None:
            self._session = Session()
            self._session.headers.update(
                {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
            )
            self._session.add_domain_limiter(TimedLimiter('descargas2020.com', '2 seconds'))
        return self._session

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return not url.endswith('.torrent') and REWRITABLE_REGEX.match(url)

    # urlrewriter API
    def url_rewrite(self, task, entry):
        entry['url'] = self.parse_download_page(entry['url'], task)

    @plugin.internet(log)
    def parse_download_page(self, url, task):
        log.verbose('Descargas2020 URL: %s', url)

        try:
            page = self.session.get(url)
        except requests.RequestException as e:
            raise UrlRewritingError(e)
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(e)

        torrent_id = None
        url_format = DESCARGAS2020_TORRENT_FORMAT

        torrent_id_prog = re.compile(
            r"(?:parametros\s*=\s*\n?)\s*{\s*\n(?:\s*'\w+'\s*:.*\n)+\s*'(?:torrentID|id)'\s*:\s*'(\d+)'"
        )
        torrent_ids = soup.findAll(text=torrent_id_prog)
        if torrent_ids:
            match = torrent_id_prog.search(torrent_ids[0])
            if match:
                torrent_id = match.group(1)
        if not torrent_id:
            log.debug('torrent ID not found, searching openTorrent script')
            match = re.search(
                r'function openTorrent.*\n.*\{.*(\n.*)+window\.location\.href =\s*\".*\/(\d+.*)\";',
                page.text,
                re.MULTILINE,
            )
            if match:
                torrent_id = match.group(2).rstrip('/')

        if not torrent_id:
            raise UrlRewritingError('Unable to locate torrent ID from url %s' % url)

        return url_format.format(torrent_id)

    def search(self, task, entry, config=None):
        if not config:
            log.debug('Descargas2020 disabled')
            return set()
        log.debug('Search Descargas2020')
        url_search = 'http://descargas2020.com/buscar'
        results = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            query = re.sub(r' \(\d\d\d\d\)$', '', query)
            log.debug('Searching Descargas2020 %s', query)
            query = unicodedata.normalize('NFD', query).encode('ascii', 'ignore')
            data = {'q': query}
            try:
                response = task.requests.post(url_search, data=data)
            except requests.RequestException as e:
                log.error('Error searching Descargas2020: %s', e)
                return results
            content = response.content
            soup = get_soup(content)
            soup2 = soup.find('ul', attrs={'class': 'buscar-list'})
            children = soup2.findAll('a', href=True)
            for child in children:
                entry = Entry()
                entry['url'] = child['href']
                entry_title = child.find('h2')
                if entry_title is None:
                    log.debug('Ignore empty entry')
                    continue
                entry_title = entry_title.text
                if not entry_title:
                    continue
                try:
                    entry_quality_lan = re.search(
                        r'.+ \[([^\]]+)\](\[[^\]]+\])+$', entry_title
                    ).group(1)
                except AttributeError:
                    log.debug('Quality not found')
                    continue
                entry_title = re.sub(r' \[.+]$', '', entry_title)
                entry['title'] = entry_title + ' ' + entry_quality_lan
                results.add(entry)
        log.debug('Finish search Descargas2020 with %d entries', len(results))
        return results


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteDescargas2020, 'descargas2020', interfaces=['urlrewriter', 'search'], api_ver=2
    )
