from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import quote

import logging
import re

from flexget import plugin
from flexget import validator
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode, clean_title
from flexget.utils.requests import TimedLimiter

log = logging.getLogger('search_sceneaccess')

CATEGORIES = {
    'browse':
        {
            'Movies/DVD-R': 8,
            'Movies/x264': 22,
            'Movies/XviD': 7,

            'TV/HD-x264': 27,
            'TV/SD-x264': 17,
            'TV/XviD': 11,

            'Games/PC': 3,
            'Games/PS3': 5,
            'Games/PSP': 20,
            'Games/WII': 28,
            'Games/XBOX360': 23,

            'APPS/ISO': 1,
            'DOX': 14,
            'MISC': 21
        },
    'nonscene':
        {
            'Movies/HD-x264': 41,
            'Movies/SD-x264': 42,
            'Movies/XviD': 43,
            'TV/HD': 44,
            'TV/SD': 45
        },
    'mp3/0day':
        {
            '0DAY/APPS': 2,
            'FLAC': 40,
            'MP3': 13,
            'MVID': 15,
        },
    'archive':
        {
            'Movies/Packs': 4,
            'TV/Packs': 26,
            'Games/Packs': 29,
            'XXX/Packs': 37,
            'Music/Packs': 38
        },
    'foreign':
        {
            'Movies/DVD-R': 31,
            'Movies/x264': 32,
            'Movies/XviD': 30,
            'TV/x264': 34,
            'TV/XviD': 33,
        },
    'xxx':
        {
            'XXX/XviD': 12,
            'XXX/x264': 35,
            'XXX/0DAY': 36
        }
}

URL = 'https://sceneaccess.eu/'


class SceneAccessSearch(object):
    """ Scene Access Search plugin

    == Basic usage:

    sceneaccess:
        username: XXXX              (required)
        password: XXXX              (required)
        category: Movies/x264       (optional)
        gravity_multiplier: 200     (optional)

    == Categories:
    +---------------+----------------+-----------+--------------+--------------+----------+
    |    browse     |    nonscene    | mp3/0day  |   archive    |   foreign    |   xxx    |
    +---------------+----------------+-----------+--------------+--------------+----------+
    | APPS/ISO      | Movies/HD-x264 | 0DAY/APPS | Games/Packs  | Movies/DVD-R | XXX/0DAY |
    | DOX           | Movies/SD-x264 | FLAC      | Movies/Packs | Movies/x264  | XXX/x264 |
    | Games/PC      | Movies/XviD    | MP3       | Music/Packs  | Movies/XviD  | XXX/XviD |
    | Games/PS3     | TV/HD          | MVID      | TV/Packs     | TV/x264      |          |
    | Games/PSP     | TV/SD          |           | XXX/Packs    | TV/XviD      |          |
    | Games/WII     |                |           |              |              |          |
    | Games/XBOX360 |                |           |              |              |          |
    | MISC          |                |           |              |              |          |
    | Movies/DVD-R  |                |           |              |              |          |
    | Movies/x264   |                |           |              |              |          |
    | Movies/XviD   |                |           |              |              |          |
    | TV/HD-x264    |                |           |              |              |          |
    | TV/SD-x264    |                |           |              |              |          |
    | TV/XviD       |                |           |              |              |          |
    +---------------+----------------+-----------+--------------+--------------+----------+

    You can combine the categories almost any way you want, here are some examples:

    category:
      archive: yes          => Will search all categories within archive section

    category: Movies/x264   => Search Movies/x264 within 'browse' section (browse is always default if unspecified)

    category:
      browse:
        - 22  => This is custom category ID
        - Movies/XviD
      foreign:
        - Movies/x264
        - Movies/XviD

    Specifying specific category ID is also possible, you can extract ID from URL, for example
    if you hover or click on category on the site you'll see similar address:

    http://sceneaccess.URL/browse?cat=22

    In this example, according to this bit ?cat=22 , category id is 22.

    == Priority

    gravity_multiplier is optional parameter that increases odds of downloading found matches from sceneaccess
    instead of other search providers, that may have higer odds due to their higher number of peers.
    Although sceneaccess does not have many peers as some public trackers, the torrents are usually faster.
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

        # Scope as in pages like `browse`, `mp3/0day`, `foreign`, etc.
        # Will only accept categories from `browse` which will it default to, unless user specifies other scopes
        # via dict
        root.accept('choice', key='category').accept_choices(CATEGORIES['browse'])
        root.accept('number', key='category')
        categories = root.accept('dict', key='category')

        category_list = root.accept('list', key='category')
        category_list.accept('choice').accept_choices(CATEGORIES['browse'])

        for category in CATEGORIES:
            categories.accept('choice', key=category).accept_choices(CATEGORIES[category])
            categories.accept('boolean', key=category)
            categories.accept('number', key=category)
            category_list = categories.accept('list', key=category)
            category_list.accept('choice', key=category).accept_choices(CATEGORIES[category])
            category_list.accept('number', key=category)
        return root

    def processCategories(self, config):
        """
        sceneaccess use different url for different supercategories (let's call them scopes)

        For example, most categories (international tv, movies, games, ...) reside within `browse` with url
        www.sceneaccess.eu/browse or mp3 and 0day releases have their own scope called `mp3/0day` but their url is
        www.sceneaccess.eu/spam

        this method iterates over all possible combinations and returns a list of dicts that contain both relative link
        to scope as well as url fragments of categories that main method search() will use:
        Return example:
        {'url_path': 'spam',
         'category_url_string': '&c40=40&c13=13'
        }
        """

        to_process = dict()
        scope = 'browse'  # Default scope to search in
        category = config.get('category')

        if category:
            if isinstance(category, dict):                          # Categories have search scope specified.
                for scope in category:
                    if isinstance(category[scope], bool):           # If provided boolean, search all categories within
                        category[scope] = []                        # the scope.
                    elif not isinstance(category[scope], list):     # or convert single category into list
                        category[scope] = [category[scope]]
                    to_process[scope] = category[scope]
            else:                       # Will default to `browse` scope, because no scope was specified (only category)
                category = [category]
                to_process[scope] = category
        else:    # Category was not set, will default to all categories within `browse` scope.
            to_process[scope] = []

        ret = list()

        for scope, categories in to_process.items():
            cat_id_list = list()

            for category in categories:
                try:
                    cat_id = CATEGORIES[scope][category]
                except KeyError:            # User provided category id directly
                    cat_id = category
                finally:
                    if isinstance(cat_id, list):
                        [cat_id_list.append(l) for l in cat_id]
                    else:
                        cat_id_list.append(cat_id)

            if scope == 'mp3/0day':     # mp3/0day is actually /spam?search= in URL, can safely change it now
                scope = 'spam'

            category_url_string = ''.join(['&c' + str(x) + '=' + str(x) for x in cat_id_list])  # &c<id>=<id>&...
            ret.append({'url_path': scope, 'category_url_string': category_url_string})
            return ret

    @plugin.internet(log)
    def search(self, task, entry, config=None):
        """
            Search for entries on SceneAccess
        """

        session = task.requests

        if 'sceneaccess.eu' not in session.domain_limiters:
            session.add_domain_limiter(TimedLimiter('sceneaccess.eu', '7 seconds'))

        if not session.cookies:
            log.debug('Logging in to %s...' % URL)
            params = {'username': config['username'],
                      'password': config['password'],
                      'submit': 'come on in'}
            session.post(URL + 'login', data=params)

        if 'gravity_multiplier' in config:
            multip = config['gravity_multiplier']
        else:
            multip = 1

        # Prepare queries...
        BASE_URLS = list()
        entries = set()
        for category in self.processCategories(config):
            BASE_URLS.append(URL + '%(url_path)s?method=2%(category_url_string)s' % category)

        # Search...
        for search_string in entry.get('search_strings', [entry['title']]):
            search_string_normalized = normalize_unicode(clean_title(search_string))
            search_string_url_fragment = '&search=' + quote(search_string_normalized.encode('utf8'))

            for url in BASE_URLS:
                url += search_string_url_fragment
                log.debug('Search URL for `%s`: %s' % (search_string, url))

                page = session.get(url).content
                soup = get_soup(page)

                for result in soup.findAll('tr', attrs={'class': 'tt_row'}):
                    entry = Entry()
                    entry['title'] = result.find('a', href=re.compile(r'details\?id=\d+'))['title']
                    entry['url'] = URL + result.find('a', href=re.compile(r'.torrent$'))['href']

                    entry['torrent_seeds'] = result.find('td', attrs={'class': 'ttr_seeders'}).text
                    entry['torrent_leeches'] = result.find('td', attrs={'class': 'ttr_leechers'}).text
                    entry['search_sort'] = torrent_availability(entry['torrent_seeds'],
                                                                entry['torrent_leeches']) * multip

                    size = result.find('td', attrs={'class': 'ttr_size'}).text
                    size = re.search('(\d+(?:[.,]\d+)*)\s?([KMG]B)', size)

                    if size:
                        if size.group(2) == 'GB':
                            entry['content_size'] = int(float(size.group(1)) * 1000 ** 3 / 1024 ** 2)
                        elif size.group(2) == 'MB':
                            entry['content_size'] = int(float(size.group(1)) * 1000 ** 2 / 1024 ** 2)
                        elif size.group(2) == 'KB':
                            entry['content_size'] = int(float(size.group(1)) * 1000 / 1024 ** 2)
                        else:
                            entry['content_size'] = int(float(size.group(1)) / 1024 ** 2)

                    entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SceneAccessSearch, 'sceneaccess', groups=['search'], api_ver=2)
