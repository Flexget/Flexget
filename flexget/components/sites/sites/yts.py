from urllib.parse import quote

from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import normalize_unicode, torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.qualities import Quality
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='yts')


class UrlRewriteYTS:
    """YTS search"""

    schema = {'type': 'boolean'}

    def search(self, task, entry, config=None):
        entries = set()
        search_strings = [
            normalize_unicode(s) for s in entry.get('search_strings', [entry['title']])
        ]
        for search_string in search_strings:
            url = 'https://yts.am/api/v2/list_movies.json?query_term=%s' % (
                quote(search_string.encode('utf-8'))
            )

            logger.debug('requesting: {}', url)

            try:
                result = requests.get(url)
                try:
                    data = result.json()
                except ValueError:
                    logger.debug('Could not decode json from response: {}', result.text)
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
                            entry['title'] = item['title_long']
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
                            entry['quality'] = Quality(f"{torrent['quality']} {torrent['type']}")
                            entry['movie_name'] = item['title']
                            entry['movie_year'] = item['year']
                            entry['imdb_id'] = item['imdb_code']
                            if entry.isvalid():
                                entries.add(entry)
            except Exception:
                logger.debug('invalid return structure from YTS')

        logger.debug('Search got {} results', len(entries))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteYTS, 'yts', interfaces=['search'], api_ver=2)
