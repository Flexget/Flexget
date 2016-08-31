from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests, json
from flexget.utils.requests import TokenBucketLimiter
from flexget.utils.search import torrent_availability

log = logging.getLogger('search_btn')


class SearchBTN(object):
    schema = {'type': 'string'}
    # Advertised limit is 150/hour (24s/request average). This may need some tweaking.
    request_limiter = TokenBucketLimiter('api.btnapps.net', 100, '25 seconds')

    def search(self, task, entry, config):
        task.requests.add_domain_limiter(self.request_limiter)
        api_key = config

        searches = entry.get('search_strings', [entry['title']])

        if 'series_name' in entry:
            search = {'category': 'Episode'}
            if 'tvdb_id' in entry:
                search['tvdb'] = entry['tvdb_id']
            elif 'tvrage_id' in entry:
                search['tvrage'] = entry['tvrage_id']
            else:
                search['series'] = entry['series_name']
            if 'series_id' in entry:
                # BTN wants an ep style identifier even for sequence shows
                if entry.get('series_id_type') == 'sequence':
                    search['name'] = 'S01E%02d' % entry['series_id']
                else:
                    search['name'] = entry['series_id'] + '%'  # added wildcard search for better results.
            searches = [search]
            # If searching by series name ending in a parenthetical, try again without it if there are no results.
            if search.get('series') and search['series'].endswith(')'):
                match = re.match('(.+)\([^\(\)]+\)$', search['series'])
                if match:
                    searches.append(dict(search, series=match.group(1).strip()))

        results = set()
        for search in searches:
            data = json.dumps({'method': 'getTorrents', 'params': [api_key, search], 'id': 1})
            try:
                r = task.requests.post('http://api.btnapps.net/',
                                       data=data, headers={'Content-type': 'application/json'})
            except requests.RequestException as e:
                log.error('Error searching btn: %s' % e)
                continue
            content = r.json()
            if not content or not content['result']:
                log.debug('No results from btn')
                if content and content.get('error'):
                    if content['error'].get('code') == -32002:
                        log.error('btn api call limit exceeded, throttling connection rate')
                        self.request_limiter.tokens = -1
                    else:
                        log.error('Error searching btn: %s' % content['error'].get('message', content['error']))
                continue
            if 'torrents' in content['result']:
                for item in content['result']['torrents'].values():
                    entry = Entry()
                    entry['title'] = item['ReleaseName']
                    entry['title'] += ' '.join(['', item['Resolution'], item['Source'], item['Codec']])
                    entry['url'] = item['DownloadURL']
                    entry['torrent_seeds'] = int(item['Seeders'])
                    entry['torrent_leeches'] = int(item['Leechers'])
                    entry['torrent_info_hash'] = item['InfoHash']
                    entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                    if item['TvdbID'] and int(item['TvdbID']):
                        entry['tvdb_id'] = int(item['TvdbID'])
                    if item['TvrageID'] and int(item['TvrageID']):
                        entry['tvrage_id'] = int(item['TvrageID'])
                    results.add(entry)
                # Don't continue searching if this search yielded results
                break
        return results


@event('plugin.register')
def register_plugin():
    plugin.register(SearchBTN, 'btn', groups=['search'], api_ver=2)
