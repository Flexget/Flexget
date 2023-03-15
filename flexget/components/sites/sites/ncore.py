import re

from loguru import logger

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.requests import TokenBucketLimiter
from flexget.utils.soup import get_soup

logger = logger.bind(name='nCore')

URL = 'https://ncore.pro'

HEADERS = {'Content-type': 'application/x-www-form-urlencoded'}

PASSKEY = ''

CATEGORIES = {
    "all",
    "xvid_hun",
    "xvid",
    "dvd_hun",
    "dvd",
    "dvd9_hun",
    "dvd9",
    "hd_hun",
    "hd",
    "xvidser_hun",
    "xvidser",
    "dvdser_hun",
    "dvdser",
    "hdser_hun",
    "hdser",
}

SORT = {
    'default': 'fid',
    'date': 'fid',
    'size': 'size',
    'seeds': 'seeders',
    'leechers': 'leechers',
    'downloads': 'times_completed',
}


class UrlRewriteNcore:
    """nCore urlrewriter."""

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'category': {
                'type': 'array',
                'items': {'type': 'string', 'enum': list(CATEGORIES)},
                'default': [],
            },
            'sort_by': {'type': 'string', 'default': 'default', 'enum': list(SORT)},
            'sort_reverse': {'type': 'boolean', 'default': False},
        },
        'required': ['username', 'password'],
        'additionalProperties': False,
    }

    request_limiter = TokenBucketLimiter('ncore.pro/', 100, '5 seconds')

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """
        Search for name from ncore.
        """

        data = {
            "set_lang": "hu",
            "submitted": "1",
            "nev": config.get("username"),
            "pass": config.get("password"),
            "ne_leptessen_ki": 0,
        }

        page = task.requests.post(URL + "/login.php", data=data, headers=HEADERS)
        soup = get_soup(page.content)
        passkey_line = str(soup.find('link', href=re.compile(r'rss\.php\?key=')))
        PASSKEY = passkey_line[passkey_line.find("key=") : passkey_line.find('"', 20, 90)]

        entries = set()

        for search_string in entry.get('search_strings', [entry['title']]):
            data = {
                "mire": search_string,
                "miben": "name",
                "miszerint": SORT[config.get('sort_by')],
            }

            if config.get('category'):
                data["kivalasztott_tipus[]"] = config.get('category')
                data["tipus"] = "kivalasztottak_kozott"
            else:
                data["tipus"] = "all_own"

            if config.get('sort_reverse'):
                data["hogyan"] = "DESC"

            page = task.requests.post(URL + "/torrents.php", data=data, headers=HEADERS)
            soup = get_soup(page.content)
            for a in soup.findAll('a', title=re.compile(".+")):
                if 'details' in a.get('href'):
                    e = Entry()

                    href = a.get('href')
                    id = href[href.find("id=") + 3 :]

                    e['title'] = a.text
                    e['url'] = URL + '/torrents.php?action=download&id={0}&'.format(id) + PASSKEY

                    parent = a.parent.parent.parent.parent

                    e['torrent_seeds'] = parent.find('div', class_='box_s2').string
                    e['torrent_leeches'] = parent.find('div', class_='box_l2').string
                    e['content_size'] = parent.find('div', class_='box_meret2').string
                    e['torrent_availability'] = torrent_availability(
                        e['torrent_seeds'], e['torrent_leeches']
                    )

                    yield e


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteNcore, 'ncore', interfaces=['search'], api_ver=2)
