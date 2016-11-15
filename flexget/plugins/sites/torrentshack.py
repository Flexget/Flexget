from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging
import re

from flexget import plugin
from flexget import validator
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode, clean_title
from flexget.utils.requests import Session
from flexget.utils.tools import parse_filesize

log = logging.getLogger('search_torrentshack')

session = Session()

CATEGORIES = {
    'Apps/PC': 100,
    'Apps/misc': 150,
    'eBooks': 180,
    'Games/PC': 200,
    'Games/PS3': 240,
    'Games/Xbox360': 260,
    'HandHeld': 280,
    'Movies/x264': 300,
    'REMUX': 320,
    'Movies/DVD-R': 350,
    'Movies/XviD': 400,
    'Music/MP3': 450,
    'Music/FLAC': 480,
    'Music/Videos': 500,
    'TV/x264-HD': 600,
    'TV/x264-SD': 620,
    'TV/DVDrip': 700,
    'Misc': 800,
    'Anime': 850,
    'Foreign': 960,
    'Full Blu-ray': 970,
    'TV-SD Pack': 980,
    'TV-HD Pack': 981,
    'Movies-HD Pack': 982,
    'Movies-SD Pack': 983,
    'MP3 Pack': 984,
    'FLAC Pack': 985,
    'Games Pack': 986
}

URL = 'http://www.torrentshack.me/'


class TorrentShackSearch(object):
    """ TorrentShack Search plugin

    == Basic usage:

    torrentshack:
        username: XXXX              (required)
        password: XXXX              (required)
        category: Movies/x264       (optional)
        type: p2p OR scene          (optional)
        gravity_multiplier: 200     (optional)

    == Categories
    +---------------+--------------+--------------+----------------+
    | Apps/PC       | Movies/x264  | TV/x264-HD   | TV-SD Pack     |
    | Apps/misc     | REMUX        | TV/x264-SD   | TV-HD Pack     |
    | eBooks        | Movies/DVD-R | TV/DVDrip    | Movies-HD Pack |
    | Games/PC      | Movies/XviD  | Misc         | Movies-SD Pack |
    | Games/PS3     | Music/MP3    | Anime        | MP3 Pack       |
    | Games/Xbox360 | Music/FLAC   | Foreign      | FLAC Pack      |
    | HandHeld      | Music/Videos | Full Blu-ray | Games Pack     |
    +---------------+--------------+--------------+----------------+

    You can specify either a single category or list of categories, example:

    category: Movies/x264

    or

    category:
        - Movies/XviD
        - Movies/x264

    Specifying specific category ID is also possible. You can extract ID from URL - for example
    if you hover or click on category on the site you'll see similar address:

    http://torrentshack.URL/torrents.php?filter_cat[300]=1

    In this particular example, category id is 300.

    == Priority

    gravity_multiplier is optional parameter that increases odds of downloading found matches from torrentshack
    instead of other search providers, that may have higer odds due to their higher number of peers.
    Although torrentshack  does not have many peers as some public trackers, the torrents are usually faster.
    By default, Flexget give higher priority to found matches according to following formula:

    gravity = number of seeds * 2 + number of leechers

    gravity_multiplier will multiply the above number by specified amount.
    If you use public trackers for searches, you may want to use this feature.
    """

    def validator(self):
        """Return config validator."""
        root = validator.factory('dict')
        root.accept('text', key='username', required=True)
        root.accept('text', key='password', required=True)
        root.accept('number', key='gravity_multiplier')
        root.accept('choice', 'type').accept_choices(['p2p', 'scene'])

        root.accept('choice', key='category').accept_choices(CATEGORIES)
        root.accept('number', key='category')
        categories = root.accept('list', key='category')
        categories.accept('choice', key='category').accept_choices(CATEGORIES)
        categories.accept('number', key='category')

        return root

    def prepare_config(self, config):
        config.setdefault('type', 'both')
        config.setdefault('gravity_multiplier', 1)
        config.setdefault('category', [])

        if not isinstance(config['category'], list):
            config['category'] = [config['category']]

        categories_id = list()
        for category in config['category']:
            if not isinstance(category, int):
                categories_id.append(CATEGORIES.get(category))
            else:
                categories_id.append(category)
        config['category'] = categories_id
        return config

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        config = self.prepare_config(config)

        if not session.cookies:
            log.debug('Logging in to %s...' % URL)
            params = {
                'username': config['username'],
                'password': config['password'],
                'keeplogged': '1',
                'login': 'Login'
            }
            session.post(URL + 'login.php', data=params)

        cat = ''.join(['&' + ('filter_cat[%s]' % id) + '=1' for id in config['category']])
        rls = 'release_type=' + config['type']
        url_params = rls + cat
        multip = config['gravity_multiplier']

        entries = set()
        for search_string in entry.get('search_strings', [entry['title']]):
            srch = normalize_unicode(clean_title(search_string))
            srch = '&searchstr=' + quote(srch.encode('utf8'))

            url = URL + 'torrents.php?' + url_params + srch
            log.debug('Fetching URL for `%s`: %s' % (search_string, url))

            page = session.get(url).content
            soup = get_soup(page)

            for result in soup.findAll('tr', attrs={'class': 'torrent'}):
                entry = Entry()
                entry['title'] = result.find('span', attrs={'class': 'torrent_name_link'}).text
                entry['url'] = URL + result.find('a', href=re.compile('torrents\.php\?action=download')).get('href')
                entry['torrent_seeds'], entry['torrent_leeches'] = [r.text for r in result.findAll('td')[-2:]]
                entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches']) * multip

                size = result.findAll('td')[-4].text
                size = re.search('(\d+(?:[.,]\d+)*)\s?([KMG]B)', size)

                entry['content_size'] = parse_filesize(size.group(0))

                entries.add(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentShackSearch, 'torrentshack', groups=['search'], api_ver=2)
