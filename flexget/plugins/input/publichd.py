from __future__ import unicode_literals, division, absolute_import

import logging
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached
from flexget.utils import requests
from werkzeug.urls import url_quote
import re

log = logging.getLogger('publichd')


class InputPublicHD(object):
    """
        Parses torrents from publichd.se

        Configuration expects the URL of a search result:
        
        publichd: https://publichd.se/index.php?page=torrents&category=14
        
    """

    schema = {
        'type': ['string', 'object'],
        # Simple form, just url
        'anyOf': [{'format': 'url'}],
        # Advanced form, with options (no options implemented yet)
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
        },
        'required': ['url'],
        'additionalProperties': False
    }

    @cached('publichd')
    @internet(log)
    def on_task_input(self, task, config):
        if isinstance(config, basestring):
            config = {'url': config}
        soup = get_soup(task.requests.get(config['url']).content)

        return self.create_entries(soup)

    @cached('publichd')
    @internet(log)
    def search(self, entry, config=None):
        if isinstance(config, basestring):
            config = {'url': config}
        url = '%s&search=%s' % (config['url'], url_quote(entry['title'], 'utf8'))
        soup = get_soup(requests.get(url).content)

        return self.create_entries(soup)

    def create_entries(self, soup):

        table = soup.find('table', id='torrbg')

        queue = []
        for tr in table.find_all('tr')[1:]:
            title_link = tr.find('a', href=re.compile(r'^index\.php\?page=torrent-details'))
            url_link = tr.find('a', href=re.compile(r'^magnet:'))
            if title_link is None or url_link is None:
                continue

            title = title_link.string
            url = url_link['href']
            log.debug('Found title "%s"', title)
            log.debug('Found url "%s"', url)
            entry = Entry(title=title, url=url)
            queue.append(entry)

        return queue

register_plugin(InputPublicHD, 'publichd', api_ver=2, groups=['search'])
