from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.components.sites.utils import torrent_availability, normalize_unicode
from flexget.utils.tools import parse_filesize

log = logging.getLogger('yts')


class UrlRewriteYTS(object):
    """YTS search"""

    schema = {'type': 'boolean'}

    def search(self, task, entry, config=None):
        entries = set()
        search_strings = [
            normalize_unicode(s) for s in entry.get('search_strings', [entry['title']])
        ]
        for search_string in search_strings:
            url = 'https://yts.am/api/v2/list_movies.json?query_term=%s' % (
                urllib.quote(search_string.encode('utf-8'))
            )

            log.debug('requesting: %s' % url)

            try:
                result = requests.get(url)
                try:
                    data = result.json()
                except ValueError:
                    log.debug('Could not decode json from response: %s', result.text)
                    raise plugin.PluginError('Error getting result from yts.')
            except requests.RequestException as e:
                raise plugin.PluginError('Could not retrieve query from yts (%s)' % e.args[0])
            if not data['status'] == 'ok':
                raise plugin.PluginError('failed to query YTS')

            try:
                if data['data']['movie_count'] > 0:
                    for item in data['data']['movies']:
                        for torrent in item['torrents']:
                            entry = Entry()
                            entry['title'] = item['title']
                            entry['year'] = item['year']
                            entry['url'] = torrent['url']
                            entry['content_size'] = parse_filesize(
                                str(torrent['size_bytes']) + "b"
                            )
                            entry['torrent_seeds'] = torrent['seeds']
                            entry['torrent_leeches'] = torrent['peers']
                            entry['torrent_info_hash'] = torrent['hash']
                            entry['torrent_availability'] = torrent_availability(
                                entry['torrent_seeds'], entry['torrent_leeches']
                            )
                            entry['quality'] = torrent['quality']
                            entry['imdb_id'] = item['imdb_code']
                            if entry.isvalid():
                                entries.add(entry)
            except Exception:
                log.debug('invalid return structure from YTS')

        log.debug('Search got %d results' % len(entries))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteYTS, 'yts', interfaces=['search'], api_ver=2)
