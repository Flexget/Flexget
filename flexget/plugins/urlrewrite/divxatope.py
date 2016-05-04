from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.plugins.plugin_urlrewriting import UrlRewritingError
from flexget.utils import requests
from flexget.utils.soup import get_soup

from flexget.entry import Entry
from flexget.utils.search import normalize_unicode

from bs4.element import Tag

log = logging.getLogger('divxatope')


class UrlRewriteDivxATope(object):
    """
    divxatope urlrewriter and search Plugin.
    """

    
    schema = {
        'type': 'boolean',
        'default': False
    }

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return (
            url.startswith('http://www.divxatope.com/descargar') or url.startswith('http://divxatope.com/descargar')
        )

    # urlrewriter API
    def url_rewrite(self, task, entry):
        # Rewrite divxatope.com/descargar/ to divxatope.com/descarga-torrent/
        entry['url'] = re.sub('/descargar', '/descarga-torrent', entry['url'])
        entry['url'] = self.parse_download_page(entry['url'])

    @plugin.internet(log)
    def parse_download_page(self, url):
        try:
            page = requests.get(url).content
            soup = get_soup(page, 'html.parser')
            download_link = soup.findAll(href=re.compile('redirect|redirectlink'))
            download_href = download_link[0]['href']
            return download_href
        except Exception:
            raise UrlRewritingError(
                'Unable to locate torrent from url %s' % url
            )

    def search(self, task, entry, config=None):
        if not config:
            log.debug('Divxatope disabled')
            return set()
        log.debug('Search DivxATope')
        url_search = 'http://www.divxatope.com/buscar/descargas/'
        results = set()
        regex = re.compile("(.+) \(\d\d\d\d\)")
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            query = regex.findall(query)[0]
            log.debug('Searching DivxATope %s' % query)
            query = query.encode('utf8', 'ignore')
            data = {'search': query}
            try:
                response = task.requests.post(url_search, data=data)
            except requests.RequestException as e:
                log.error('Error searching DivxATope: %s' % e)
                return
            content = response.content
            
            soup = get_soup(content)
            soup2 = soup.find('ul', attrs={'class': 'peliculas-box'})
            children = soup2.findAll('a', href=True)
            for child in children:
                entry = Entry()
                entry['url'] = child['href']
                entry_title = child.find('h2').contents[0]
                quality_lan = child.find('strong').contents
                log.debug(len(quality_lan))
                if len(quality_lan) > 2:
                    if (isinstance(quality_lan[0],Tag)):
                        entry_quality_lan = quality_lan[1]
                    else:
                        entry_quality_lan = quality_lan[0] + ' ' + quality_lan[2]
                elif len(quality_lan) == 2:
                    entry_quality_lan = quality_lan[1]
                entry['title'] = entry_title + ' ' + entry_quality_lan
                results.add(entry)
        log.debug('Finish search DivxATope with %d entries' % len(results))
        return results


@event('plugin.register')
def register_plugin():
    plugin.register(
        UrlRewriteDivxATope,
        'divxatope',
        groups=['urlrewriter', 'search'],
        api_ver=2
    )
