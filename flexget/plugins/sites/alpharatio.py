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
from flexget.config_schema import one_or_more
from flexget.utils.tools import parse_filesize

log = logging.getLogger('alpharatio')
Base = db_schema.versioned_base('alpharatio', 0)

requests = RequestSession()
requests.add_domain_limiter(TimedLimiter('alpharatio.cc', '5 seconds'))
# ElementZero confirmed with AlphaRato sysop 'jasonmaster' that they do want a 5 second limiter

CATEGORIES = {
    'tvsd': 'filter_cat[1]',
    'tvhd': 'filter_cat[2]',
    'tvdvdrip': 'filter_cat[3]',
    'tvpacksd': 'filter_cat[4]',
    'tvpackhd': 'filter_cat[5]',
    'moviesd': 'filter_cat[6]',
    'moviehd': 'filter_cat[7]',
    'moviepacksd': 'filter_cat[8]',
    'moviepackhd': 'filter_cat[9]',
    'moviexxx': 'filter_cat[10]',
    'mvid': 'filter_cat[11]',
    'gamespc': 'filter_cat[12]',
    'gamesxbox': 'filter_cat[13]',
    'gamesps3': 'filter_cat[14]',
    'gameswii': 'filter_cat[15]',
    'appspc': 'filter_cat[16]',
    'appsmac': 'filter_cat[17]',
    'appslinux': 'filter_cat[18]',
    'appsmobile': 'filter_cat[19]',
    '0dayXXX': 'filter_cat[20]',
    'ebook': 'filter_cat[21]',
    'audiobook': 'filter_cat[22]',
    'music': 'filter_cat[23]',
    'misc': 'filter_cat[24]'
}

LEECHSTATUS = {
    'normal': 0,
    'freeleech': 1,
    'neutral leech': 2,
    'either': 3
}


class AlphaRatioCookie(Base):
    __tablename__ = 'alpharatio_cookie'

    username = Column(Unicode, primary_key=True)
    _cookie = Column('cookie', Unicode)
    cookie = json_synonym('_cookie')
    expires = Column(DateTime)


class SearchAlphaRatio(object):
    """
        AlphaRatio search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': one_or_more({'type': 'string', 'enum': list(CATEGORIES.keys())}, unique_items=True),
            'order_by': {'type': 'string', 'enum': ['seeders', 'leechers', 'time', 'size', 'year', 'snatched'],
                         'default': 'time'},
            'order_desc': {'type': 'boolean', 'default': True},
            'scene': {'type': 'boolean'},
            'leechstatus': {'type': 'string', 'enum': list(LEECHSTATUS.keys()), 'default': 'normal'},
        },
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    base_url = 'https://alpharatio.cc/'
    errors = False

    def get(self, url, params, username, password, force=False):
        """
        Wrapper to allow refreshing the cookie if it is invalid for some reason

        :param unicode url:
        :param dict params:
        :param str username:
        :param str password:
        :param bool force: flag used to refresh the cookie forcefully ie. forgo DB lookup
        :return:
        """
        cookies = self.get_login_cookie(username, password, force=force)

        response = requests.get(url, params=params, cookies=cookies)

        if self.base_url + 'login.php' in response.url:
            if self.errors:
                raise plugin.PluginError('AlphaRatio login cookie is invalid. Login page received?')
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
                saved_cookie = session.query(AlphaRatioCookie).filter(AlphaRatioCookie.username == username).first()
                if saved_cookie and saved_cookie.expires and saved_cookie.expires >= datetime.datetime.now():
                    log.debug('Found valid login cookie')
                    return saved_cookie.cookie

        url = self.base_url + 'login.php'
        try:
            log.debug('Attempting to retrieve AlphaRatio cookie')
            response = requests.post(url, data={'username': username, 'password': password, 'login': 'Log in',
                                                'keeplogged': '1'}, timeout=30)
        except RequestException as e:
            raise plugin.PluginError('AlphaRatio login failed: %s', e)

        if 'Your username or password was incorrect.' in response.text:
            raise plugin.PluginError('AlphaRatio login failed: Your username or password was incorrect.')

        with Session() as session:
            expires = None
            for c in requests.cookies:
                if c.name == 'session':
                    expires = c.expires
            if expires:
                expires = datetime.datetime.fromtimestamp(expires)
            log.debug('Saving or updating AlphaRatio cookie in db')
            cookie = AlphaRatioCookie(username=username, cookie=dict(requests.cookies), expires=expires)
            session.merge(cookie)
            return cookie.cookie

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on AlphaRatio
        """
        params = {}

        if 'category' in config:
            categories = config['category'] if isinstance(config['category'], list) else [config['category']]
            for category in categories:
                params[CATEGORIES[category]] = 1

        if 'scene' in config:
            params['scene'] = int(config['scene'])

        ordering = 'desc' if config['order_desc'] else 'asc'

        entries = set()

        params.update({'order_by': config['order_by'], 'search_submit': 1, 'action': 'basic', 'order_way': ordering,
                       'freeleech': LEECHSTATUS[config['leechstatus']]})

        for search_string in entry.get('search_strings', [entry['title']]):
            params['searchstr'] = search_string
            log.debug('Using search params: %s', params)
            try:
                page = self.get(self.base_url + 'torrents.php', params, config['username'], config['password'])
                log.debug('requesting: %s', page.url)
            except RequestException as e:
                log.error('AlphaRatio request failed: %s', e)
                continue

            soup = get_soup(page.content)
            for result in soup.findAll('tr', attrs={'class': 'torrent'}):
                group_info = result.find('td', attrs={'class': 'big_info'}).find('div', attrs={'class': 'group_info'})
                title = group_info.find('a', href=re.compile('torrents.php\?id=\d+')).text
                url = self.base_url + \
                    group_info.find('a', href=re.compile('torrents.php\?action=download(?!usetoken)'))['href']

                torrent_info = result.findAll('td')
                log.debug('AlphaRatio size: %s', torrent_info[5].text)
                size = re.search('(\d+(?:[.,]\d+)*)\s?([KMGTP]B)', torrent_info[4].text)
                torrent_tags = ', '.join([tag.text for tag in group_info.findAll('div', attrs={'class': 'tags'})])

                e = Entry()

                e['title'] = title
                e['url'] = url
                e['torrent_tags'] = torrent_tags
                e['content_size'] = parse_filesize(size.group(0))
                e['torrent_snatches'] = int(torrent_info[5].text)
                e['torrent_seeds'] = int(torrent_info[6].text)
                e['torrent_leeches'] = int(torrent_info[7].text)

                entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchAlphaRatio, 'alpharatio', groups=['search'], api_ver=2)
