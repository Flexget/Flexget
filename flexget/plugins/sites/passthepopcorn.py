from __future__ import unicode_literals, division, absolute_import

import datetime
import logging

from requests.exceptions import TooManyRedirects
from sqlalchemy import Column, Unicode, DateTime
from dateutil.parser import parse as dateutil_parse

from flexget import plugin, db_schema
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import json_synonym
from flexget.utils.requests import Session as RequestSession, TimedLimiter, RequestException
from flexget.utils.tools import parse_filesize

log = logging.getLogger('passthepopcorn')
Base = db_schema.versioned_base('passthepopcorn', 1)

requests = RequestSession()
requests.add_domain_limiter(TimedLimiter('passthepopcorn.me', '5 seconds'))

TAGS = [
    'action',
    'adventure',
    'animation',
    'arthouse',
    'asian',
    'biography',
    'camp',
    'comedy',
    'crime',
    'cult',
    'documentary',
    'drama',
    'experimental',
    'exploitation',
    'family',
    'fantasy',
    'film.noir',
    'history',
    'horror',
    'martial.arts',
    'musical',
    'mystery',
    'performance',
    'philosophy',
    'politics',
    'romance',
    'sci.fi',
    'short',
    'silent',
    'sport',
    'thriller',
    'video.art',
    'war',
    'western'
]

ORDERING = {
    'Relevance': 'relevance',
    'Time added': 'timeadded',
    'Time w/o reseed': 'timenoreseed',
    'First time added': 'creationtime',
    'Year': 'year',
    'Title': 'title',
    'Size': 'size',
    'Snatched': 'snatched',
    'Seeders': 'seeders',
    'Leechers': 'leechers',
    'Runtime': 'runtime',
    'IMDb rating': 'imdb',
    'IMDb vote count': 'imdbvotes',
    'PTP rating': 'ptprating',
    'PTP vote count': 'ptpvotes',
    'MC rating': 'mc',
    'RT rating': 'rt',
    'Bookmark count': 'bookmarks'
}

RELEASE_TYPES = {
    'non-scene': 0,
    'scene': 1,
    'golden popcorn': 2
}


@db_schema.upgrade('passthepopcorn')
def upgrade(ver, session):
    if ver is None:
        ver = 0
    if ver == 0:
        raise db_schema.UpgradeImpossible
    return ver


class PassThePopcornCookie(Base):
    __tablename__ = 'passthepopcorn_cookie'

    username = Column(Unicode, primary_key=True)
    _cookie = Column('cookie', Unicode)
    cookie = json_synonym('_cookie')
    expires = Column(DateTime)


class SearchPassThePopcorn(object):
    """
        PassThePopcorn search plugin.
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'passkey': {'type': 'string'},
            'tags': one_or_more({'type': 'string', 'enum': TAGS}, unique_items=True),
            'order_by': {'type': 'string', 'enum': list(ORDERING.keys()),
                         'default': 'Time added'},
            'order_desc': {'type': 'boolean', 'default': True},
            'freeleech': {'type': 'boolean'},
            'release_type': {'type': 'string', 'enum': list(RELEASE_TYPES.keys())}
        },
        'required': ['username', 'password', 'passkey'],
        'additionalProperties': False
    }

    base_url = 'https://passthepopcorn.me/'
    errors = False

    def get(self, url, params, username, password, passkey, force=False):
        """
        Wrapper to allow refreshing the cookie if it is invalid for some reason

        :param unicode url: the url to be requested
        :param dict params: request params
        :param str username:
        :param str password:
        :param str passkey: the user's private passkey
        :param bool force: flag used to refresh the cookie forcefully ie. forgo DB lookup
        :return:
        """
        cookies = self.get_login_cookie(username, password, passkey, force=force)
        invalid_cookie = False

        try:
            response = requests.get(url, params=params, cookies=cookies)
            if self.base_url + 'login.php' in response.url:
                invalid_cookie = True
        except TooManyRedirects:
            # TODO Apparently it endlessly redirects if the cookie is invalid? I assume it's a gazelle bug.
            log.debug('PassThePopcorn request failed: Too many redirects. Invalid cookie?')
            invalid_cookie = True
        except RequestException as e:
            if e.response and e.response.status_code == 429:
                log.error('Saved cookie is invalid and will be deleted. Error: %s', str(e))
                # cookie is invalid and must be deleted
                with Session() as session:
                    session.query(PassThePopcornCookie).filter(PassThePopcornCookie.username == username).delete()
                invalid_cookie = True
            else:
                log.error('PassThePopcorn request failed: %s', str(e))

        if invalid_cookie:
            if self.errors:
                raise plugin.PluginError('PassThePopcorn login cookie is invalid. Login page received?')
            self.errors = True
            # try again
            response = self.get(url, params, username, password, passkey, force=True)
        else:
            self.errors = False

        return response

    def get_login_cookie(self, username, password, passkey, force=False):
        """
        Retrieves login cookie

        :param str username:
        :param str password:
        :param str passkey: the user's private passkey
        :param bool force: if True, then retrieve a fresh cookie instead of looking in the DB
        :return:
        """
        if not force:
            with Session() as session:
                saved_cookie = session.query(PassThePopcornCookie).filter(PassThePopcornCookie.username == username)\
                    .first()
                if saved_cookie and saved_cookie.expires and saved_cookie.expires >= datetime.datetime.now():
                    log.debug('Found valid login cookie')
                    return saved_cookie.cookie

        url = self.base_url + 'ajax.php'
        params = {
            'username': username,
            'password': password,
            'login': 'Login',
            'keeplogged': '1',
            'passkey': passkey,
            'action': 'login'
        }
        try:
            log.debug('Attempting to retrieve PassThePopcorn cookie')
            requests.post(url, data=params, timeout=30)
        except RequestException as e:
            raise plugin.PluginError('PassThePopcorn login failed: %s' % e)

        with Session() as session:
            expires = datetime.datetime.now() + datetime.timedelta(days=30)
            log.debug('Saving or updating PassThePopcorn cookie in db. Expires 30 days from now: %s', expires)
            cookie = PassThePopcornCookie(username=username, cookie=dict(requests.cookies), expires=expires)
            session.merge(cookie)
            return cookie.cookie

    @plugin.internet(log)
    def search(self, task, entry, config):
        """
            Search for entries on PassThePopcorn
        """
        params = {}

        if 'tags' in config:
            tags = config['tags'] if isinstance(config['tags'], list) else [config['tags']]
            params['taglist'] = ',+'.join(tags)
        
        release_type = config.get('release_type')
        if release_type:
            params['scene'] = RELEASE_TYPES[release_type]

        if config.get('freeleech'):
            params['freetorrent'] = int(config['freeleech'])

        ordering = 'desc' if config['order_desc'] else 'asc'

        entries = set()

        params.update({
            'order_by': ORDERING[config['order_by']],
            'order_way': ordering,
            'action': 'advanced',
            'json': 'noredirect'
        })

        search_strings = entry.get('search_strings', [entry['title']])

        # searching with imdb id is much more precise
        if entry.get('imdb_id'):
            search_strings = [entry['imdb_id']]

        for search_string in search_strings:
            params['searchstr'] = search_string
            log.debug('Using search params: %s', params)
            try:
                result = self.get(self.base_url + 'torrents.php', params, config['username'], config['password'],
                                  config['passkey']).json()
            except RequestException as e:
                log.error('PassThePopcorn request failed: %s', e)
                continue

            total_results = result['TotalResults']
            log.debug('Total results: %s', total_results)

            authkey = result['AuthKey']
            passkey = result['PassKey']

            for movie in result['Movies']:
                # skip movies that are irrelevant
                if entry.get('movie_year') and int(movie['Year']) != int(entry['movie_year']):
                    log.debug('Movie year %s does not match %s', movie['Year'], entry['movie_year'])
                    continue
                # imdb id in the json result is without 'tt'
                if entry.get('imdb_id') and movie['ImdbId'] not in entry['imdb_id']:
                    log.debug('imdb id %s does not match %s', movie['ImdbId'], entry['imdb_id'])
                    continue

                for torrent in movie['Torrents']:
                    e = Entry()

                    e['title'] = torrent['ReleaseName']

                    e['torrent_tags'] = movie['Tags']
                    e['content_size'] = parse_filesize(torrent['Size'] + ' b')
                    e['torrent_snatches'] = int(torrent['Snatched'])
                    e['torrent_seeds'] = int(torrent['Seeders'])
                    e['torrent_leeches'] = int(torrent['Leechers'])
                    e['torrent_id'] = int(torrent['Id'])
                    e['golden_popcorn'] = torrent['GoldenPopcorn']
                    e['checked'] = torrent['Checked']
                    e['uploaded_at'] = dateutil_parse(torrent['UploadTime'])

                    e['url'] = self.base_url + 'torrents.php?action=download&id={}&authkey={}&torrent_pass={}'.format(
                        e['torrent_id'], authkey, passkey
                    )

                    entries.add(e)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchPassThePopcorn, 'passthepopcorn', interfaces=['search'], api_ver=2)
