from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import datetime
import re

from sqlalchemy import Column, Unicode, DateTime

from flexget import plugin, db_schema
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import TimedLimiter, RequestException
from flexget.manager import Session
from flexget.utils.database import json_synonym
from flexget.utils.requests import Session as RequestSession
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

log = logging.getLogger('filelist')
Base = db_schema.versioned_base('filelist', 0)

requests = RequestSession()
requests.add_domain_limiter(TimedLimiter('filelist.ro', '2 seconds'))

BASE_URL = 'https://filelist.ro/'

CATEGORIES = {
    'all': 0,
    'anime': 24,
    'audio': 11,
    'cartoons': 15,
    'docs': 16,
    'games console': 10,
    'games pc': 9,
    'linux': 17,
    'misc': 18,
    'mobile': 22,
    'movies 3d': 25,
    'movies bluray': 20,
    'movies dvd': 2,
    'movies dvd-ro': 3,
    'movies hd': 4,
    'movies hd-ro': 19,
    'movies sd': 1,
    'series hd': 21,
    'series sd': 23,
    'software': 8,
    'sport': 13,
    'tv': 14,
    'videoclip': 12,
    'xxx': 7
}

SORTING = {
    'hybrid': 0,
    'relevance': 1,
    'date': 2,
    'size': 3,
    'snatches': 4,
    'peers': 5
}

SEARCH_IN = {
    'both': 0,
    'title': 1,
    'description': 2
}


class FileListCookie(Base):
    __tablename__ = 'filelist_cookie'

    username = Column(Unicode, primary_key=True)
    _cookie = Column('cookie', Unicode)
    cookie = json_synonym('_cookie')
    expires = Column(DateTime)


class SearchFileList(object):
    """
        FileList.ro search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'passkey': {'type': 'string'},
            'category': {'type': 'string', 'enum': list(CATEGORIES.keys()), 'default': 'all'},
            'order_by': {'type': 'string', 'enum': list(SORTING.keys()), 'default': 'hybrid'},
            'order_ascending': {'type': 'boolean', 'default': False},
            'search_in': {'type': 'string', 'enum': list(SEARCH_IN.keys()), 'default': 'both'},
            'include_dead': {'type': 'boolean', 'default': False}
        },
        'required': ['username', 'password', 'passkey'],
        'additionalProperties': False
    }

    errors = False

    def get(self, url, params, username, password, force=False):
        """
        Wrapper to allow refreshing the cookie if it is invalid for some reason

        :param str url:
        :param list params:
        :param str username:
        :param str password:
        :param bool force: flag used to refresh the cookie forcefully ie. forgo DB lookup
        :return:
        """
        cookies = self.get_login_cookie(username, password, force=force)

        response = requests.get(url, params=params, cookies=cookies)

        if 'login.php' in response.url:
            if self.errors:
                raise plugin.PluginError('FileList.ro login cookie is invalid. Login page received?')
            self.errors = True
            # try again
            response = self.get(url, params, username, password, force=True)
        else:
            self.errors = False

        return response

    def get_login_cookie(self, username, password, force=False):
        """
        Retrieves login cookie

        :param str username:
        :param str password:
        :param bool force: if True, then retrieve a fresh cookie instead of looking in the DB
        :return:
        """
        if not force:
            with Session() as session:
                saved_cookie = session.query(FileListCookie).filter(FileListCookie.username == username.lower()).first()
                if saved_cookie and saved_cookie.expires and saved_cookie.expires >= datetime.datetime.now():
                    log.debug('Found valid login cookie')
                    return saved_cookie.cookie

        url = BASE_URL + 'takelogin.php'
        try:
            log.debug('Attempting to retrieve FileList.ro cookie')
            response = requests.post(url, data={'username': username, 'password': password, 'login': 'Log in',
                                                'unlock': '1'}, timeout=30)
        except RequestException as e:
            raise plugin.PluginError('FileList.ro login failed: %s' % e)

        if 'https://filelist.ro/my.php' != response.url:
            raise plugin.PluginError('FileList.ro login failed: Your username or password was incorrect.')

        with Session() as session:
            expires = None
            for c in requests.cookies:
                if c.name == 'pass':
                    expires = c.expires
            if expires:
                expires = datetime.datetime.fromtimestamp(expires)
            log.debug('Saving or updating FileList.ro cookie in db')
            cookie = FileListCookie(username=username.lower(), cookie=dict(requests.cookies), expires=expires)
            session.merge(cookie)
            return cookie.cookie

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on FileList.ro
        """
        entries = set()

        params = {
            'cat': CATEGORIES[config['category']],
            'incldead': int(config['include_dead']),
            'order_by': SORTING[config['order_by']],
            'searchin': SEARCH_IN[config['search_in']],
            'asc': int(config['order_ascending'])
        }

        for search_string in entry.get('search_strings', [entry['title']]):
            params['search'] = search_string
            log.debug('Using search params: %s', params)
            try:
                page = self.get(BASE_URL + 'browse.php', params, config['username'], config['password'])
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('FileList.ro request failed: %s', e)
                continue

            soup = get_soup(page.content)
            for result in soup.findAll('div', attrs={'class': 'torrentrow'}):
                e = Entry()

                torrent_info = result.findAll('div', attrs={'class': 'torrenttable'})

                # genres
                genres = torrent_info[1].find('font')
                if genres:
                    genres = genres.text.lstrip('[').rstrip(']').replace(' ', '')
                    genres = genres.split('|')

                tags = torrent_info[1].findAll('img')
                freeleech = False
                internal = False
                for tag in tags:
                    if tag.get('alt', '').lower() == 'freeleech':
                        freeleech = True
                    if tag.get('alt', '').lower() == 'internal':
                        internal = True

                title = torrent_info[1].find('a').get('title')
                # this is a dirty fix to get the full title since their developer is a moron
                if re.match("\<img src=\'.*\'\>", title):
                    title = torrent_info[1].find('b').text
                    # if the title is shortened, then do a request to get the full one :(
                    if title.endswith('...'):
                        url = BASE_URL + torrent_info[1].find('a')['href']
                        try:
                            request = self.get(url, {}, config['username'], config['password'])
                        except RequestException as e:
                            log.error('FileList.ro request failed: %s', e)
                            continue
                        title_soup = get_soup(request.content)
                        title = title_soup.find('div', attrs={'class': 'cblock-header'}).text

                e['title'] = title
                e['url'] = BASE_URL + torrent_info[3].find('a')['href'] + '&passkey=' + config['passkey']
                e['content_size'] = parse_filesize(torrent_info[6].find('font').text)

                e['torrent_snatches'] = int(torrent_info[7].find('font').text.replace(' ', '').replace('times', '')
                                            .replace(',', ''))
                e['torrent_seeds'] = int(torrent_info[8].find('span').text)
                e['torrent_leeches'] = int(torrent_info[9].find('span').text)
                e['torrent_internal'] = internal
                e['torrent_freeleech'] = freeleech
                if genres:
                    e['torrent_genres'] = genres

                entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchFileList, 'filelist', interfaces=['search'], api_ver=2)
