from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import re

from sqlalchemy import Column, Unicode, Integer, PickleType, DateTime
from requests.utils import dict_from_cookiejar, cookiejar_from_dict
from datetime import datetime, timedelta

from flexget import plugin
from flexget import validator
from flexget.db_schema import versioned_base
from flexget.manager import Session
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.search import torrent_availability, normalize_unicode

log = logging.getLogger('sceneaccess')
Base = versioned_base('cookies_sceneaccess', 0)

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
            'MISC': 21,

            # Bundles
            'Movies': [8, 22, 7],
            'TV': [27, 17, 11],
            'Games': [3, 5, 20, 28, 23]
        },
    'mp3/0day':
        {
            '0DAY/APPS': 2,
            'FLAC': 40,
            'MP3': 13,
            'MVID': 15,

            # Bundles
            'Music': [40, 13]
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

            # Bundles
            'Movies': [30, 31, 32],
            'TV': [33, 34]
        },
    'xxx':
        {
            'XXX/XviD': 12,
            'XXX/x264': 35,
            'XXX/0DAY': 36
        }
}

URL = 'https://sceneaccess.eu/'


class SceneAccessDatabase(Base):
    __tablename__ = 'cookies_sceneaccess'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    username = Column(Unicode, index=True)
    cookiejar = Column(PickleType)
    expires = Column(DateTime)


class SceneAccessAuth(object):
    def __init__(self, username, password):
        self.session = requests.Session()
        self.url = URL
        self.username = username
        self.password = password
        self.db_session = Session()

        self.force_login = False

    def Authenticate(self):
        db = self.db_session.query(SceneAccessDatabase).filter(
            SceneAccessDatabase.username == self.username).first()

        if db:
            if db.expires < datetime.now() or self.force_login is True:
                log.debug('Cookies expired...')
                self.db_session.delete(db)
                self.db_session.commit()
                self._login()
            else:
                log.debug('Cookies loaded from database')
                cookiejar = cookiejar_from_dict(db.cookiejar)
                self.session.add_cookiejar(cookiejar)
        else:
            self._login()

        return self.session

    def _login(self):
        params = {'password': self.password,
                  'username': self.username,
                  'submit': 'come on in'
        }
        _url = self.url + 'login'
        log.debug('Logging in...')
        self.session.post(_url, data=params)
        cookiejar = dict_from_cookiejar(self.session.cookies)
        self.db_session.add(SceneAccessDatabase(
            username=self.username, cookiejar=cookiejar, expires=datetime.now() + timedelta(days=7)
        ))
        self.db_session.commit()

class SceneAccessSearch(object):
    """ Scene Access Search plugin

        Required fields: `login` and `password`
        Optional fields: `within` and `category`

        category can be either category name (all of the categories are named exactly as they appear on SceneAccess),
            name of the "bundle" they belong to, or category id directly

        available "bundles": Movies, TV

        Usage examples:

            sceneaccess:
                login: Flexget
                password: Flexget

            ... Will search default SceneAccess `browse` page in all categories

            sceneaccess:
                login: Flexget
                password: Flexget
                category: TV
    """

    def validator(self):
        """Return config validator."""
        root = validator.factory('dict')
        root.accept('text', key='username', required=True)
        root.accept('text', key='password', required=True)

        # Scope as in pages like `browse`, `mp3/0day`, `foreign`, etc.
        # Will only accept categories from `browse` which will it default to, unless user specifies other scopes
        # via dict
        root.accept('choice', key='category').accept_choices(CATEGORIES['browse'], ignore_case=True)
        categories = root.accept('dict', key='category')

        category_list = root.accept('list', key='category')
        category_list.accept('choice').accept_choices(CATEGORIES['browse'], ignore_case=True)

        for category in CATEGORIES:
            categories.accept('choice', key=category).accept_choices(CATEGORIES[category], ignore_case=True)
            categories.accept('boolean', key=category)
            category_list = categories.accept('list', key=category)
            category_list.accept('choice', key=category).accept_choices(CATEGORIES[category], ignore_case=True)
        return root

    def processCategories(self, config):
        toProcess = dict()

        # Build request urls from config
        try:
            scope = 'browse' # Default scope to search in
            category = config['category']
            if isinstance(category, dict):                          # Categories have search scope specified.
                for scope in category:
                    if isinstance(category[scope], bool):           # If provided boolean, search all categories
                        category[scope] = []
                    elif not isinstance(category[scope], list):     # Convert single category into list
                        category[scope] = [category[scope]]
                    toProcess[scope] = category[scope]
            else:                       # Single category specified, will default to `browse` scope.
                category = [category]
                toProcess[scope] = category

        except KeyError:    # Category was not set, will default to `browse` scope and all categories.
            toProcess[scope] = []

        finally:    # Process the categories to be actually in usable format for search() method
            ret = list()

            for scope, categories in toProcess.iteritems():
                cat_id = list()

                for category in categories:
                    id = CATEGORIES[scope][category]
                    if isinstance(id, list):
                        [cat_id.append(l) for l in id]
                    else:
                        cat_id.append(id)

                if scope == 'mp3/0day':     # mp3/0day is actually /spam?search= in URL, can safely change it now
                    scope = 'spam'

                category_url_string = ''.join(['&c' + str(id) + '=' + str(id) for id in cat_id])  # &c<id>=<id>&...
                ret.append({'url_path': scope, 'category_url_string': category_url_string})
            return ret

    @plugin.internet(log)
    def search(self, entry, config=None):
        """
            Search for entries on SceneAccess
        """

        SCC = SceneAccessAuth(config['username'], config['password'])
        session = SCC.Authenticate()

        BASE_URLS = list()
        entries = set()
        for category in self.processCategories(config):
            BASE_URLS.append(URL + '%(url_path)s?method=2%(category_url_string)s' % category)

        for search_string in entry.get('search_strings', [entry['title']]):
            search_string_normalized = normalize_unicode(search_string)
            search_string_url_fragment = '&search=' + urllib.quote(search_string_normalized.encode('utf8'))

            for url in BASE_URLS:
                url += search_string_url_fragment
                log.debug('Search URL for `%s`: %s' % (search_string, url))

                page = session.get(url).content
                soup = get_soup(page)

                for result in soup.findAll('tr', attrs={'class': 'tt_row'}):
                    entry = Entry()
                    entry['title'] = result.find('a', href=re.compile(r'details\?id=\d+'))['title']
                    entry['url'] = URL + result.find('a', href=re.compile(r'.torrent$'))['href']

                    entry['torrent_seeds'] = result.find('td', attrs={'class': 'ttr_seeders'}).string
                    entry['torrent_leeches'] = result.find('td', attrs={'class': 'ttr_leechers'}).string
                    entry['search_sort'] = torrent_availability(entry['torrent_seeds'], entry['torrent_leeches'])

                    size = result.find('td', attrs={'class': 'ttr_size'}).next
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