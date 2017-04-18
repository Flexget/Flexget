from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests, json
from flexget.utils.search import torrent_availability

log = logging.getLogger('ptp')

session = requests.Session()
# The site will block your IP for a couple of hours if too many requests are made within a certain period, which seems
# to be quite short, so the domain delay has been set low enough to allow continuous requesting.
session.set_domain_delay('tls.passthepopcorn.me', '9 seconds')
base_url = 'https://tls.passthepopcorn.me'


class SearchPTP(object):

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'passkey': {'type': 'string'}
        },
        'required': ['username', 'password', 'passkey'],
        'additionalProperties': False
    }

    def search(self, task, entry, config):
        session.post(
            '%s/ajax.php?action=login' % base_url,
            data={
                'username': config['username'],
                'password': config['password'],
                'passkey': config['passkey'],
                'keeplogged': '1',
                'login': 'Login'}
        )

        search = entry['title']
        if 'imdb_id' in entry:
            search = entry['imdb_id']

        try:
            r = session.post('%s/torrents.php?json=1&searchstr=%s' % (base_url, search))
        except RequestException as e:
            log.error('Error searching PTP: %s' % e)
            return
        try:
            content = json.loads(r.content)
        except ValueError as e:
            log.debug('No results from PTP.')
            return

        results = set()
        if 'Torrents' in content:
            for item in content['Torrents']:
                entry  = Entry()
                entry['title'] = item['ReleaseName']
                entry['url'] = '%s/torrents.php?action=download&id=%s&authkey=%s&torrent_pass=%s' \
                                   % (base_url, item['Id'], content['AuthKey'], content['PassKey'])
                entry['imdb_id'] = 'tt%s' % str(content['ImdbId']).zfill()
                entry['ptp_checked'] = item['Checked']
                entry['ptp_gp'] = item['GoldenPopcorn']
                entry['ptp_scene'] = item['Scene']
                entry['torrent_seeds'] = int(item['Seeders'])
                entry['torrent_leeches'] = int(item['Leechers'])
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])
                results.add(entry)

        return results


@event('plugin.register')
def register_plugin():
    plugin.register(SearchPTP, 'ptp', groups=['search'], api_ver=2)
