from datetime import datetime
from enum import Enum, unique
from typing import List, Optional, Tuple

from loguru import logger
from requests import Request
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests_html import HTML, Element
from sqlalchemy import Column, DateTime, Unicode

from flexget import db_schema, plugin
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import json_synonym
from flexget.utils.requests import RequestException
from flexget.utils.requests import Session as RequestSession
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='hebits')
Base = db_schema.versioned_base('hebits', 0)

requests = RequestSession()


@unique
class HEBitsCategory(Enum):
    pc_games = 21
    console_games = 33
    hd_movies = 27
    bluray = 36
    dvdr = 20
    sd_movies = 19
    il_movies = 25
    top_imdb = 34
    hd_shows = 1
    hd_shows_subs = 24
    il_hd_shows = 37
    il_shows = 7
    animated = 23
    music = 28
    flac_music = 31
    il_music = 6
    concerts = 35
    soundtrack = 30
    mobile = 32
    ebooks = 26
    apps = 22
    misc = 29
    xxx = 9
    sport = 41


class HEBitsSort(Enum):
    names = 1
    files = 2
    comments = 3
    date = 4
    size = 5
    completed = 6
    uploaders = 7
    downloaders = 8
    uploader = 9


class HEBitsCookies(Base):
    __tablename__ = 'hebits_cookies'

    user_name = Column(Unicode, primary_key=True)
    _cookies = Column('cookies', Unicode)
    cookies = json_synonym('_cookies')
    expires = Column(DateTime)


class SearchHeBits:
    """
        HEBits search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'user_name': {'type': 'string'},
            'password': {'type': 'string'},
            'category': {'type': 'string', 'enum': [value.name for value in HEBitsCategory]},
            'free': {'type': 'boolean'},
            'double': {'type': 'boolean'},
            'triple': {'type': 'boolean'},
            'pack': {'type': 'boolean'},
            'order_by': {
                'type': 'string',
                'enum': [value.name for value in HEBitsSort],
                'default': HEBitsSort.date.name,
            },
            'order_desc': {'type': 'boolean', 'default': True},
        },
        'required': ['user_name', 'password'],
        'additionalProperties': False,
    }

    base_url = 'https://hebits.net/'
    login_url = f"{base_url}takeloginAjax.php"
    search_url = f"{base_url}browse.php"
    download_url = f"{base_url}downloadRss.php"
    profile_link = f"{base_url}my.php"

    @staticmethod
    def _extract_passkey(user_profile_html: HTML) -> str:
        """Extracts the passkey from the user profile"""
        logger.debug('trying to extract passkey')
        for tr in user_profile_html.find("tr"):
            td = tr.find("td.pror", first=True)
            if not td:
                continue
            if td.full_text == "פאסקי":
                logger.debug('succesfully extracted passkey')
                return tr.find("td.prol", first=True).text
        raise plugin.PluginError('Could not fetch passkey from user profile, did the page change?')

    @staticmethod
    def save_cookies_to_db(user_name: str, cookies: RequestsCookieJar):
        logger.debug('Saving or updating HEBits cookie in db')
        expires = datetime.fromtimestamp(list(cookies)[0].expires)
        with Session() as session:
            cookie = HEBitsCookies(user_name=user_name, cookies=dict(cookies), expires=expires)
            session.merge(cookie)

    @staticmethod
    def load_cookies_from_db(user_name: str) -> Optional[RequestsCookieJar]:
        logger.debug('Trying to load hebits cookies from DB')
        with Session() as session:
            saved_cookie = (
                session.query(HEBitsCookies).filter(HEBitsCookies.user_name == user_name).first()
            )
            if saved_cookie and saved_cookie.expires and saved_cookie.expires >= datetime.now():
                logger.debug('Found valid login cookie')
                return cookiejar_from_dict(saved_cookie.cookies)

    def login(self, user_name: str, password: str) -> RequestsCookieJar:
        data = dict(username=user_name, password=password)
        logger.debug('Trying to login to hebits with user name {}', user_name)
        rsp = requests.post(self.login_url, data=data)
        if rsp.text != 'OK':
            raise plugin.PluginError('Could not connect to HEBits, invalid credentials')
        return rsp.cookies

    def user_profile(self) -> bytes:
        logger.debug('Fetching user profile')
        rsp = requests.get(self.profile_link)
        if "returnto" in rsp.url:
            raise plugin.PluginError('Could not fetch passkey from user profile, layout change?')
        return rsp.content

    def authenticate(self, config: dict) -> str:
        """Tried to fetch cookies from DB and fallback to login if fails. Returns passkey from user profile"""
        user_name = config['user_name']
        password = config['password']

        cookies = self.load_cookies_from_db(user_name=user_name)
        if cookies:
            requests.add_cookiejar(cookies)
        else:
            cookies = self.login(user_name, password)
            self.save_cookies_to_db(user_name=user_name, cookies=cookies)

        user_profile_content = self.user_profile()
        user_profile_html = HTML(html=user_profile_content)
        passkey = self._extract_passkey(user_profile_html)
        return passkey

    @staticmethod
    def _extract_id(links: set) -> str:
        for link in links:
            if 'id=' in link:
                return link.split('=')[-1]

    @staticmethod
    def _fetch_bonus(elements: List[Element]) -> Tuple[bool, bool, bool]:
        src_text = [e.attrs["src"] for e in elements]
        freeleech = "/pic/free.jpg" in src_text
        triple_up = "/pic/triple.jpg" in src_text
        double_up = "/pic/double.jpg" in src_text
        return freeleech, double_up, triple_up

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """Search for entries on HEBits"""
        passkey = self.authenticate(config)
        params = {}

        if 'category' in config:
            params['cata'] = HEBitsCategory[config['category']].value

        entries = set()
        params['sort'] = HEBitsSort[config['order_by']].value
        params['type'] = 'desc' if config['order_desc'] else 'asc'
        for value in ('free', 'double', 'triple', 'pack'):
            if config.get(value):
                params[value] = 'on'

        for search_string in entry.get('search_strings', [entry['title']]):
            params['search'] = search_string
            logger.debug('Using search params: {}', params)
            try:
                page = requests.get(self.search_url, params=params)
                page.raise_for_status()
            except RequestException as e:
                logger.error('HEBits request failed: {}', e)
                continue

            html = HTML(html=page.content)
            table = html.find("div.browse", first=True)
            if not table:
                logger.debug(
                    'Could not find any results matching {} using the requested params {}',
                    search_string,
                    params,
                )
                continue

            all_results = table.find("div.lineBrown, div.lineGray, div.lineBlue, div.lineGreen")
            if not all_results:
                raise plugin.PluginError(
                    'Result table found but not with any known items, layout change?'
                )

            for result in all_results:
                torrent_id = self._extract_id(result.links)
                seeders = int(result.find("div.bUping", first=True).text)
                leechers = int(result.find("div.bDowning", first=True).text)
                size_text = "".join(
                    e.element.tail for e in result.find("div.bSize", first=True).find("br")
                )
                size = parse_filesize(size_text)
                title_element = result.find("div.bTitle", first=True)
                title = title_element.find("b", first=True).text.split("/")[-1].strip()
                images = title_element.find("span > img")
                freeleech, double_up, triple_up = self._fetch_bonus(images)
                req = Request(
                    'GET', url=self.download_url, params={'passkey': passkey, 'id': torrent_id}
                ).prepare()

                entry = Entry(
                    torrent_seeds=seeders,
                    torrent_leeches=leechers,
                    torrent_availability=torrent_availability(seeders, leechers),
                    content_size=size,
                    title=title,
                    freeleech=freeleech,
                    triple_up=triple_up,
                    double_up=double_up,
                    url=req.url,
                )
                entries.add(entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchHeBits, 'hebits', interfaces=['search'], api_ver=2)
