import datetime
import re

from loguru import logger
from requests.exceptions import TooManyRedirects
from sqlalchemy import Column, DateTime, Unicode

from flexget import db_schema, plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import json_synonym
from flexget.utils.requests import RequestException
from flexget.utils.requests import Session as RequestSession
from flexget.utils.requests import TimedLimiter
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='alpharatio')
Base = db_schema.versioned_base('alpharatio', 0)

requests = RequestSession()
requests.add_domain_limiter(TimedLimiter('alpharatio.cc', '5 seconds'))
# ElementZero confirmed with AlphaRato sysop 'jasonmaster' that they do want a 5 second limiter

CATEGORIES = {
    'tvsd': 'filter_cat[1]',
    'tvhd': 'filter_cat[2]',
    'tvuhd': 'filter_cat[3]',
    'tvdvdrip': 'filter_cat[4]',
    'tvpacksd': 'filter_cat[5]',
    'tvpackhd': 'filter_cat[6]',
    'tvpackuhd': 'filter_cat[7]',
    'moviesd': 'filter_cat[8]',
    'moviehd': 'filter_cat[9]',
    'movieuhd': 'filter_cat[10]',
    'moviepacksd': 'filter_cat[11]',
    'moviepackhd': 'filter_cat[12]',
    'moviepackuhd': 'filter_cat[13]',
    'moviexxx': 'filter_cat[14]',
    'bluray': 'filter_cat[15]',
    'animesd': 'filter_cat[16]',
    'animehd': 'filter_cat[17]',
    'gamespc': 'filter_cat[18]',
    'gamesxbox': 'filter_cat[19]',
    'gamesps': 'filter_cat[20]',
    'gamesnin': 'filter_cat[21]',
    'appswindows': 'filter_cat[22]',
    'appsmac': 'filter_cat[23]',
    'appslinux': 'filter_cat[24]',
    'appsmobile': 'filter_cat[25]',
    'filter_cat[0]dayXXX': 'filter_cat[26]',
    'ebook': 'filter_cat[27]',
    'audiobook': 'filter_cat[28]',
    'music': 'filter_cat[29]',
    'misc': 'filter_cat[30]',
}

LEECHSTATUS = {'normal': 0, 'freeleech': 1, 'neutral leech': 2, 'either': 3}


class AlphaRatioCookie(Base):
    __tablename__ = 'alpharatio_cookie'

    username = Column(Unicode, primary_key=True)
    _cookie = Column('cookie', Unicode)
    cookie = json_synonym('_cookie')
    expires = Column(DateTime)


class SearchAlphaRatio:
    """
    AlphaRatio search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': one_or_more(
                {'type': 'string', 'enum': list(CATEGORIES.keys())}, unique_items=True
            ),
            'order_by': {
                'type': 'string',
                'enum': ['seeders', 'leechers', 'time', 'size', 'year', 'snatched'],
                'default': 'time',
            },
            'order_desc': {'type': 'boolean', 'default': True},
            'scene': {'type': 'boolean'},
            'leechstatus': {
                'type': 'string',
                'enum': list(LEECHSTATUS.keys()),
                'default': 'normal',
            },
        },
        'required': ['username', 'password'],
        'additionalProperties': False,
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
        invalid_cookie = False

        try:
            response = requests.get(url, params=params, cookies=cookies)
            if self.base_url + 'login.php' in response.url:
                invalid_cookie = True
        except TooManyRedirects:
            # Apparently it endlessly redirects if the cookie is invalid?
            logger.debug('MoreThanTV request failed: Too many redirects. Invalid cookie?')
            invalid_cookie = True

        if invalid_cookie:
            if self.errors:
                raise plugin.PluginError(
                    'AlphaRatio login cookie is invalid. Login page received?'
                )
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
                saved_cookie = (
                    session.query(AlphaRatioCookie)
                    .filter(AlphaRatioCookie.username == username)
                    .first()
                )
                if (
                    saved_cookie
                    and saved_cookie.expires
                    and saved_cookie.expires >= datetime.datetime.now()
                ):
                    logger.debug('Found valid login cookie')
                    return saved_cookie.cookie

        url = self.base_url + 'login.php'
        try:
            logger.debug('Attempting to retrieve AlphaRatio cookie')
            response = requests.post(
                url,
                data={
                    'username': username,
                    'password': password,
                    'login': 'Log in',
                    'keeplogged': '1',
                },
                timeout=30,
            )
        except RequestException as e:
            raise plugin.PluginError('AlphaRatio login failed: %s' % e)

        if 'Your username or password was incorrect.' in response.text:
            raise plugin.PluginError(
                'AlphaRatio login failed: Your username or password was incorrect.'
            )

        with Session() as session:
            expires = None
            for c in requests.cookies:
                if c.name == 'session':
                    expires = c.expires
            if expires:
                expires = datetime.datetime.fromtimestamp(expires)
            logger.debug('Saving or updating AlphaRatio cookie in db')
            cookie = AlphaRatioCookie(
                username=username, cookie=dict(requests.cookies), expires=expires
            )
            session.merge(cookie)
            return cookie.cookie

    def find_index(self, soup, text):
        """Finds the index of the tag containing the text"""
        for i in range(0, len(soup)):
            img = soup[i].find('img')
            if soup[i].text.strip() == '' and img and text.lower() in img.get('title').lower():
                return i
            elif text.lower() in soup[i].text.lower():
                return i

        raise plugin.PluginError(
            'AlphaRatio layout has changed, unable to parse correctly. Please open a Github issue'
        )

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
        Search for entries on AlphaRatio
        """
        params = {}

        if 'category' in config:
            categories = (
                config['category']
                if isinstance(config['category'], list)
                else [config['category']]
            )
            for category in categories:
                params[CATEGORIES[category]] = 1

        if 'scene' in config:
            params['scene'] = int(config['scene'])

        ordering = 'desc' if config['order_desc'] else 'asc'

        entries = set()

        params.update(
            {
                'order_by': config['order_by'],
                'search_submit': 1,
                'action': 'basic',
                'order_way': ordering,
                'freeleech': LEECHSTATUS[config['leechstatus']],
            }
        )

        for search_string in entry.get('search_strings', [entry['title']]):
            params['searchstr'] = search_string
            logger.debug('Using search params: {}', params)
            try:
                page = self.get(
                    self.base_url + 'torrents.php', params, config['username'], config['password']
                )
                logger.debug('requesting: {}', page.url)
            except RequestException as e:
                logger.error('AlphaRatio request failed: {}', e)
                continue

            soup = get_soup(page.content)

            # extract the column indices
            header_soup = soup.find('tr', attrs={'class': 'colhead'})
            if not header_soup:
                logger.debug("no search results found for '{}'", search_string)
                continue
            header_soup = header_soup.findAll('td')

            size_idx = self.find_index(header_soup, 'size')
            snatches_idx = self.find_index(header_soup, 'snatches')
            seeds_idx = self.find_index(header_soup, 'seeders')
            leeches_idx = self.find_index(header_soup, 'leechers')

            for result in soup.findAll('tr', attrs={'class': 'torrent'}):
                group_info = result.find('td', attrs={'class': 'big_info'}).find(
                    'div', attrs={'class': 'group_info'}
                )
                title = group_info.find('a', href=re.compile(r'torrents.php\?id=\d+')).text
                url = (
                    self.base_url
                    + group_info.find(
                        'a', href=re.compile(r'torrents.php\?action=download(?!usetoken)')
                    )['href']
                )

                torrent_info = result.findAll('td')
                size_col = torrent_info[size_idx].text
                logger.debug('AlphaRatio size: {}', size_col)
                size = re.search(r'(\d+(?:[.,]\d+)*)\s?([KMGTP]B)', size_col)
                torrent_tags = ', '.join(
                    [tag.text for tag in group_info.findAll('div', attrs={'class': 'tags'})]
                )

                e = Entry()

                e['title'] = title
                e['url'] = url
                e['torrent_tags'] = torrent_tags
                if not size:
                    logger.debug(
                        'No size found! Please create a Github issue. Size received: {}', size_col
                    )
                else:
                    e['content_size'] = parse_filesize(size.group(0))

                mappings_int = {
                    'torrent_snatches': snatches_idx,
                    'torrent_seeds': seeds_idx,
                    'torrent_leeches': leeches_idx,
                }

                for dest, src in mappings_int.items():
                    if not src in torrent_info:
                        continue

                    # Some values are tagged with a ',' insted of a '.', replace them
                    value = torrent_info[src].text.replace(',', '.')

                    try:
                        e[dest] = int(value)
                    except ValueError as e:
                        logger.debug('Invalid \'{}\' with \'{}\'', dest, value)
                        continue

                entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchAlphaRatio, 'alpharatio', interfaces=['search'], api_ver=2)
