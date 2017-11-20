from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import PY3

import csv
import logging
import re
from collections import MutableSet
from datetime import datetime

from requests.exceptions import RequestException

from sqlalchemy import Column, Unicode, String
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import plugin, db_schema
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.manager import Session
from flexget.utils.database import json_synonym
from flexget.utils.requests import Session as RequestSession, TimedLimiter
from flexget.utils.soup import get_soup

log = logging.getLogger('imdb_list')
IMMUTABLE_LISTS = ['ratings', 'checkins']

Base = db_schema.versioned_base('imdb_list', 0)

MOVIE_TYPES = ['feature film', 'documentary', 'tv movie', 'video', 'short film']
SERIES_TYPES = ['tv series', 'mini-series']
OTHER_TYPES = ['video game']


class IMDBListUser(Base):
    __tablename__ = "imdb_list_user"

    user_id = Column(String, primary_key=True)
    user_name = Column(Unicode)
    _cookies = Column('cookies', Unicode)
    cookies = json_synonym('_cookies')

    lists = relation('IMDBListList', backref='imdb_user', cascade='all, delete, delete-orphan')

    def __init__(self, user_name, user_id, cookies):
        self.user_name = user_name
        self.user_id = user_id
        self.cookies = cookies


class IMDBListList(Base):
    __tablename__ = "imdb_list_lists"

    list_id = Column(Unicode, primary_key=True)
    list_name = Column(Unicode)
    user_id = Column(String, ForeignKey('imdb_list_user.user_id'))

    def __init__(self, list_id, list_name, user_id):
        self.list_id = list_id
        self.list_name = list_name
        self.user_id = user_id


if PY3:
    csv_reader = csv.reader
else:
    def csv_reader(iterable, dialect='excel', *args, **kwargs):
        """
        Compatibilty function to make python 2 act like python 3
        Always takes and returns text (no bytes).
        """
        iterable = (l.encode('utf-8') for l in iterable)
        for row in csv.reader(iterable):
            yield [cell.decode('utf-8') for cell in row]


class ImdbEntrySet(MutableSet):
    schema = {
        'type': 'object',
        'properties': {
            'login': {'type': 'string'},
            'password': {'type': 'string'},
            'list': {'type': 'string'},
            'force_language': {'type': 'string', 'default': 'en-us'}
        },
        'additionalProperties': False,
        'required': ['login', 'password', 'list']
    }

    def __init__(self, config):
        self.config = config
        self._session = RequestSession()
        self._session.add_domain_limiter(TimedLimiter('imdb.com', '5 seconds'))
        self._session.headers.update({'Accept-Language': config.get('force_language', 'en-us')})
        self.user_id = None
        self.list_id = None
        self.cookies = None
        self._items = None
        self._authenticated = False

    @property
    def session(self):
        if not self._authenticated:
            self.authenticate()
        return self._session

    def authenticate(self):
        """Authenticates a session with IMDB, and grabs any IDs needed for getting/modifying list."""
        cached_credentials = False
        with Session() as session:
            user = session.query(IMDBListUser).filter(IMDBListUser.user_name == self.config.get('login')).one_or_none()
            if user and user.cookies and user.user_id:
                log.debug('login credentials found in cache, testing')
                self.cookies = user.cookies
                self.user_id = user.user_id
                r = self._session.head('http://www.imdb.com/profile', allow_redirects=False, cookies=self.cookies)
                if not r.headers.get('location') or 'login' in r.headers['location']:
                    log.debug('cache credentials expired')
                else:
                    cached_credentials = True
            if not cached_credentials:
                log.debug('user credentials not found in cache or outdated, fetching from IMDB')
                url_credentials = (
                    'https://www.imdb.com/ap/signin?openid.return_to=https%3A%2F%2Fwww.imdb.com%2Fap-signin-'
                    'handler&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&'
                    'openid.assoc_handle=imdb_mobile_us&openid.mode=checkid_setup&openid.claimed_id=http%3A%'
                    '2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.ope'
                    'nid.net%2Fauth%2F2.0'
                )
                try:
                    r = self._session.get(url_credentials)
                except RequestException as e:
                    raise PluginError(e.args[0])
                soup = get_soup(r.content)
                inputs = soup.select('form#ap_signin_form input')
                data = dict((i['name'], i.get('value')) for i in inputs if i.get('name'))
                data['email'] = self.config['login']
                data['password'] = self.config['password']
                action = soup.find('form', id='ap_signin_form').get('action')
                log.debug('email=%s, password=%s', data['email'], data['password'])
                self._session.headers.update({'Referer': url_credentials})
                d = self._session.post(action, data=data)
                self._session.headers.update({'Referer': 'http://www.imdb.com/'})
                # Get user id by extracting from redirect url
                r = self._session.head('http://www.imdb.com/profile', allow_redirects=False)
                if not r.headers.get('location') or 'login' in r.headers['location']:
                    raise plugin.PluginError('Login to IMDB failed. Check your credentials.')
                self.user_id = re.search('ur\d+(?!\d)', r.headers['location']).group()
                self.cookies = dict(d.cookies)
                # Get list ID
            if user:
                for list in user.lists:
                    if self.config['list'] == list.list_name:
                        log.debug('found list ID %s matching list name %s in cache', list.list_id, list.list_name)
                        self.list_id = list.list_id
            if not self.list_id:
                log.debug('could not find list ID in cache, fetching from IMDB')
                if self.config['list'] == 'watchlist':
                    data = {'consts[]': 'tt0133093', 'tracking_tag': 'watchlistRibbon'}
                    wl_data = self._session.post('http://www.imdb.com/list/_ajax/watchlist_has', data=data,
                                                 cookies=self.cookies).json()
                    try:
                        self.list_id = wl_data['list_id']
                    except KeyError:
                        raise PluginError('No list ID could be received. Please initialize list by '
                                          'manually adding an item to it and try again')
                elif self.config['list'] in IMMUTABLE_LISTS or self.config['list'].startswith('ls'):
                    self.list_id = self.config['list']
                else:
                    data = {'tconst': 'tt0133093'}
                    list_data = self._session.post('http://www.imdb.com/list/_ajax/wlb_dropdown', data=data,
                                                   cookies=self.cookies).json()
                    for li in list_data['items']:
                        if li['wlb_text'] == self.config['list']:
                            self.list_id = li['data_list_id']
                            break
                    else:
                        raise plugin.PluginError('Could not find list %s' % self.config['list'])

            user = IMDBListUser(self.config['login'], self.user_id, self.cookies)
            list = IMDBListList(self.list_id, self.config['list'], self.user_id)
            user.lists.append(list)
            session.merge(user)

        self._authenticated = True

    def invalidate_cache(self):
        self._items = None

    @property
    def items(self):
        if self._items is None:
            log.debug('fetching items from IMDB')
            try:
                r = self.session.get('http://www.imdb.com/list/export?list_id=%s&author_id=%s' %
                                     (self.list_id, self.user_id), cookies=self.cookies)

            except RequestException as e:
                raise PluginError(e.args[0])
            lines = r.iter_lines(decode_unicode=True)
            # Throw away first line with headers
            next(lines)
            self._items = []
            for row in csv_reader(lines):
                log.debug('parsing line from csv: %s', ', '.join(row))
                if not len(row) == 16:
                    log.debug('no movie row detected, skipping. %s', ', '.join(row))
                    continue
                entry = Entry({
                    'title': '%s (%s)' % (row[5], row[11]) if row[11] != '????' else '%s' % row[5],
                    'url': row[15],
                    'imdb_id': row[1],
                    'imdb_url': row[15],
                    'imdb_list_position': int(row[0]),
                    'imdb_list_created': datetime.strptime(row[2], '%a %b %d %H:%M:%S %Y') if row[2] else None,
                    'imdb_list_modified': datetime.strptime(row[3], '%a %b %d %H:%M:%S %Y') if row[3] else None,
                    'imdb_list_description': row[4],
                    'imdb_name': row[5],
                    'imdb_year': int(row[11]) if row[11] != '????' else None,
                    'imdb_score': float(row[9]) if row[9] else None,
                    'imdb_user_score': float(row[8]) if row[8] else None,
                    'imdb_votes': int(row[13]) if row[13] else None,
                    'imdb_genres': [genre.strip() for genre in row[12].split(',')]
                })
                item_type = row[6].lower()
                name = row[5]
                year = int(row[11]) if row[11] != '????' else None
                if item_type in MOVIE_TYPES:
                    entry['movie_name'] = name
                    entry['movie_year'] = year
                elif item_type in SERIES_TYPES:
                    entry['series_name'] = name
                    entry['series_year'] = year
                elif item_type in OTHER_TYPES:
                    entry['title'] = name
                else:
                    log.verbose('Unknown IMDB type entry received: %s. Skipping', item_type)
                    continue
                self._items.append(entry)
        return self._items

    @property
    def immutable(self):
        if self.config['list'] in IMMUTABLE_LISTS:
            return '%s list is not modifiable' % self.config['list']

    def _from_iterable(cls, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    def __contains__(self, entry):
        return self.get(entry) is not None

    def __iter__(self):
        return iter(self.items)

    def discard(self, entry):
        if self.config['list'] in IMMUTABLE_LISTS:
            raise plugin.PluginError('%s lists are not modifiable' % ' and '.join(IMMUTABLE_LISTS))
        if 'imdb_id' not in entry:
            log.warning('Cannot remove %s from imdb_list because it does not have an imdb_id', entry['title'])
            return
        # Get the list item id
        item_ids = None
        if self.config['list'] == 'watchlist':
            data = {'consts[]': entry['imdb_id'], 'tracking_tag': 'watchlistRibbon'}
            status = self.session.post('http://www.imdb.com/list/_ajax/watchlist_has', data=data,
                                       cookies=self.cookies).json()
            item_ids = status.get('has', {}).get(entry['imdb_id'])
        else:
            data = {'tconst': entry['imdb_id']}
            status = self.session.post('http://www.imdb.com/list/_ajax/wlb_dropdown', data=data,
                                       cookies=self.cookies).json()
            for a_list in status['items']:
                if a_list['data_list_id'] == self.list_id:
                    item_ids = a_list['data_list_item_ids']
                    break
        if not item_ids:
            log.warning('%s is not in list %s, cannot be removed', entry['imdb_id'], self.list_id)
            return
        data = {
            'action': 'delete',
            'list_id': self.list_id,
            'ref_tag': 'title'
        }
        for item_id in item_ids:
            log.debug('found movie %s with ID %s in list %s, removing', entry['title'], entry['imdb_id'], self.list_id)
            self.session.post('http://www.imdb.com/list/_ajax/edit', data=dict(data, list_item_id=item_id),
                              cookies=self.cookies)
            # We don't need to invalidate our cache if we remove the item
            self._items = [i for i in self._items if i['imdb_id'] != entry['imdb_id']] if self._items else None

    def _add(self, entry):
        """Submit a new movie to imdb. (does not update cache)"""
        if self.config['list'] in IMMUTABLE_LISTS:
            raise plugin.PluginError('%s lists are not modifiable' % ' and '.join(IMMUTABLE_LISTS))
        if 'imdb_id' not in entry:
            log.warning('Cannot add %s to imdb_list because it does not have an imdb_id', entry['title'])
            return
        # Manually calling authenticate to fetch list_id and cookies
        self.authenticate()
        data = {
            'const': entry['imdb_id'],
            'list_id': self.list_id,
            'ref_tag': 'title'
        }
        log.debug('adding title %s with ID %s to imdb %s', entry['title'], entry['imdb_id'], self.list_id)
        self.session.post('http://www.imdb.com/list/_ajax/edit', data=data, cookies=self.cookies)

    def add(self, entry):
        self._add(entry)
        # Invalidate the cache so that we get the canonical entry from the imdb list
        self.invalidate_cache()

    def __ior__(self, entries):
        for entry in entries:
            self._add(entry)
        self.invalidate_cache()
        return self

    def __len__(self):
        return len(self.items)

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return True

    def get(self, entry):
        if not entry.get('imdb_id'):
            log.debug('entry %s does not have imdb_id, cannot compare to imdb list items', entry)
            return None
        log.debug('finding %s in imdb list', entry['imdb_id'])
        for e in self.items:
            if e['imdb_id'] == entry['imdb_id']:
                return e
        log.debug('could not find %s in imdb list items', entry['imdb_id'])
        return None


class ImdbList(object):
    schema = ImdbEntrySet.schema

    @staticmethod
    def get_list(config):
        return ImdbEntrySet(config)

    def on_task_input(self, task, config):
        return list(self.get_list(config))


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbList, 'imdb_list', api_ver=2, interfaces=['task', 'list'])
