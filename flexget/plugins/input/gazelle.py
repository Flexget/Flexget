from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, String, Unicode

from flexget import db_schema, plugin
from flexget.components.sites.utils import normalize_unicode
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.utils.database import json_synonym
from flexget.utils.requests import TokenBucketLimiter
from flexget.utils.tools import parse_filesize

DETECT_2FA = "Authenticator Code", "TOTP code"
logger = logger.bind(name='gazelle')
Base = db_schema.versioned_base('gazelle_session', 0)


class GazelleSession(Base):
    __tablename__ = 'gazelle_session'

    username = Column(Unicode, primary_key=True)
    base_url = Column(String, primary_key=True)

    authkey = Column(String)
    passkey = Column(String)
    _cookies = Column('cookie', Unicode)
    cookies = json_synonym('_cookies')
    expires = Column(DateTime)


class InputGazelle:
    """A generic plugin that searches a Gazelle-based website

    Limited functionality but should work for almost all of them.
    """

    def __init__(self):
        """Set up a plugin that only has the ability to do about basic search"""
        self.base_url = None

        # Aliases for config -> api params
        # Extended in subclasses
        self.aliases = {"search": "searchstr"}

        # API parameters
        # None means a raw value entry (no validation other than schema)
        # A dict means an enum with a config -> api mapping
        # A list is an enum with no mapping
        # Extended in subclasses
        self.params = {"searchstr": None}

    @property
    def schema(self):
        """The schema of the plugin

        Subclasses should extend this to implement more params
        """
        schema = {
            'type': 'object',
            'properties': {
                'base_url': {'type': 'string'},
                'username': {'type': 'string'},
                'password': {'type': 'string'},
                'max_pages': {'type': 'integer'},
                'search': {'type': 'string'},
            },
            'required': ['username', 'password'],
            'additionalProperties': False,
        }
        # base_url is only required if the subclass doesn't set it
        if not self.base_url:
            schema['required'].append('base_url')
        return schema

    def _key(self, key):
        """Gets the API key name from the entered key"""
        if key in self.aliases:
            return self.aliases[key]
        return key

    def _opts(self, key):
        """Gets the options for the specified key"""
        return self.params[self._key(key)]

    def _getval(self, key, val):
        """Gets the value for the specified key based on a config option"""
        opts = self._opts(key)
        if isinstance(opts, dict):
            # Translate the input value to the API value
            # The str cast converts bools to 'True'/'False' for use as keys
            # This allows for options that have True/False/Other values
            return opts[str(val)]
        elif isinstance(val, list):
            # Fix yaml parser making a list out of a string
            return ",".join(val)
        return val

    def params_from_config(self, config):
        """Filter params and map config values -> api values"""
        ret = {}
        for k, v in config.items():
            key = self._key(k)
            if key in self.params:
                ret[key] = self._getval(k, v)
        return ret

    def setup(self, task, config):
        """Set up a session and log in"""
        self._session = task.requests
        base_url = config.get('base_url', "").rstrip("/")
        if base_url:
            if self.base_url and self.base_url != base_url:
                logger.warning(
                    'Using plugin designed for {} on {} - things may break',
                    self.base_url,
                    base_url,
                )
            self.base_url = base_url

        if not self.base_url:
            raise PluginError("No 'base_url' configured")

        # Any more than 5 pages is probably way too loose of a search
        self.max_pages = config.get('max_pages', 5)

        # The consistent request limiting rule seems to be:
        # "Refrain from making more than five (5) requests every ten (10) seconds"
        self._session.add_domain_limiter(TokenBucketLimiter(self.base_url, 2, '2 seconds'))

        self.username = config['username']
        self.password = config['password']

        # Login
        self.authenticate()

        # Logged in successfully, it's ok if nothing matches now
        task.no_entries_ok = True

    def resume_session(self):
        """Resume an existing session from the datebase

        Return True on successful recovery, False otherwise
        """
        logger.debug("Attempting to find an existing session in the DB")
        with Session() as session:
            db_session = (
                session.query(GazelleSession)
                .filter(
                    GazelleSession.base_url == self.base_url,
                    GazelleSession.username == self.username,
                )
                .one_or_none()
            )
            if db_session and db_session.expires and db_session.expires >= datetime.utcnow():
                # Found a valid session in the DB - use it
                self._session.cookies.update(db_session.cookies)
                self.authkey = db_session.authkey
                self.passkey = db_session.passkey
                return True
        return False

    def save_current_session(self):
        """Store the current session in the database so it can be resumed later"""
        logger.debug("Storing session info in the DB")
        with Session() as session:
            expires = None
            for c in self._session.cookies:
                if c.name == "session":
                    expires = datetime.utcfromtimestamp(c.expires)
            db_session = GazelleSession(
                username=self.username,
                base_url=self.base_url,
                cookies=dict(self._session.cookies),
                expires=expires,
                authkey=self.authkey,
                passkey=self.passkey,
            )
            session.merge(db_session)

    def authenticate(self, force=False):
        """Log in and store auth data from the server

        Adapted from https://github.com/isaaczafuta/whatapi
        """
        # clean slate before creating/restoring cookies
        self._session.cookies.clear()

        if not force and self.resume_session():
            logger.info('Logged into {} using cached session', self.base_url)
            return

        # Forcing a re-login or no session in DB - log in using provided creds
        url = f"{self.base_url}/login.php"
        data = {'username': self.username, 'password': self.password, 'keeplogged': 1}
        r = self._session.post(url, data=data, allow_redirects=False, raise_status=True)
        if not r.is_redirect or r.next.url != f"{self.base_url}/index.php":
            msg = f"Failed to log into {self.base_url}"
            for otp_text in DETECT_2FA:
                # TODO: Find a better signal that 2FA is enabled
                if otp_text in r.text:
                    msg += " - Accounts using 2FA are currently not supported"
                    break
            raise PluginError(msg)

        account_info = self.request(no_login=True, action='index')
        self.authkey = account_info['authkey']
        self.passkey = account_info['passkey']
        logger.info('Logged in to {}', self.base_url)

        # Store the session so we can resume it later
        self.save_current_session()

    def request(self, no_login=False, **params):
        """Make an AJAX request to the API

        If `no_login` is True, logging in will not be attempted if the request
        is redirected to the login page.

        Adapted from https://github.com/isaaczafuta/whatapi
        """
        if 'action' not in params:
            raise ValueError("An 'action' is required when making a request")

        ajaxpage = f"{self.base_url}/ajax.php"
        r = self._session.get(ajaxpage, params=params, allow_redirects=False, raise_status=True)
        if not no_login and r.is_redirect and r.next.url == f"{self.base_url}/login.php":
            logger.warning("Redirected to login page, reauthenticating and trying again")
            self.authenticate(force=True)
            return self.request(no_login=True, **params)

        if r.status_code != 200:
            raise PluginError(f"{self.base_url} returned a non-200 status code")

        try:
            json_response = r.json()
            if json_response['status'] != "success":
                # Try to deal with errors returned by the API
                error = json_response.get('error', json_response.get('status'))
                if not error or error == "failure":
                    error = json_response.get('response', str(json_response))

                raise PluginError(f"{self.base_url} gave a failure response of '{error}'")
            return json_response['response']
        except (ValueError, TypeError, KeyError):
            raise PluginError(f"{self.base_url} returned an invalid response")

    def search_results(self, params):
        """Generator that yields search results"""
        page = 1
        pages = None
        while page <= self.max_pages:
            if pages and page >= pages:
                break

            logger.debug('Attempting to get page {} of search results', page)
            result = self.request(action='browse', page=page, **params)
            if not result['results']:
                break
            yield from result['results']

            pages = result.get('pages', pages)
            page += 1

        if page > self.max_pages:
            logger.warning('Stopped after {} pages (out of {} total pages)', self.max_pages, pages)

    def get_entries(self, search_results):
        """Generator that yields Entry objects from search results"""
        for result in search_results:
            # Get basic information on the release
            info = {k: result[k] for k in ('groupId', 'groupName')}

            # Releases can have multiple download options
            for tor in result['torrents']:
                temp = info.copy()
                temp['torrentId'] = tor['torrentId']

                yield Entry(
                    title="{groupName} ({groupId} - {torrentId}).torrent".format(**temp),
                    url="{}/torrents.php?action=download&id={}&authkey={}&torrent_pass={}"
                    "".format(self.base_url, temp['torrentId'], self.authkey, self.passkey),
                    torrent_seeds=tor['seeders'],
                    torrent_leeches=tor['leechers'],
                    # Size is returned in bytes
                    content_size=parse_filesize(str(tor['size']) + "b"),
                )

    @plugin.internet(logger)
    def search(self, task, entry, config):
        """Search interface"""
        self.setup(task, config)

        entries = set()
        params = self.params_from_config(config)
        for search_string in entry.get('search_strings', [entry['title']]):
            query = normalize_unicode(search_string)
            params[self._key('search')] = query
            entries.update(self.get_entries(self.search_results(params)))
        return entries

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        """Task input interface"""
        self.setup(task, config)

        params = self.params_from_config(config)
        return self.get_entries(self.search_results(params))


class InputGazelleMusic(InputGazelle):
    """A plugin that searches a Gazelle-based music website

    Based on https://github.com/WhatCD/Gazelle since it's the starting point of
    all Gazelle-based music sites.
    """

    def __init__(self):
        """Set up the majority of parameters that these sites support"""
        super().__init__()

        self.aliases.update(
            {
                "artist": "artistname",
                "album": "groupname",
                "leech_type": "freetorrent",
                "release_type": "releasetype",
                "tags": "taglist",
                "tag_type": "tags_type",
                "log": "haslog",
            }
        )

        self.params.update(
            {
                "taglist": None,
                "artistname": None,
                "groupname": None,
                "year": None,
                "tags_type": {"any": 0, "all": 1},
                "encoding": [
                    "192",
                    "APS (VBR)",
                    "V2 (VBR)",
                    "V1 (VBR)",
                    "256",
                    "APX (VBR)",
                    "V0 (VBR)",
                    "q8.x (VBR)",
                    "320",
                    "Lossless",
                    "24bit Lossless",
                    "Other",
                ],
                "format": ["MP3", "FLAC", "Ogg Vorbis", "AAC", "AC3", "DTS"],
                "media": ["CD", "DVD", "Vinyl", "Soundboard", "SACD", "DAT", "Cassette", "WEB"],
                "releasetype": {
                    "album": 1,
                    "soundtrack": 3,
                    "EP": 5,
                    "anthology": 6,
                    "compilation": 7,
                    "single": 9,
                    "live album": 11,
                    "remix": 13,
                    "bootleg": 14,
                    "interview": 15,
                    "mixtape": 16,
                    "unknown": 21,
                },
                "haslog": {"False": 0, "True": 1, "100%": 100, "<100%": -1},
                "freetorrent": {"freeleech": 1, "neutral": 2, "either": 3, "normal": 0},
                "hascue": {"False": 0, "True": 1},
                "scene": {"False": 0, "True": 1},
                "vanityhouse": {"False": 0, "True": 1},
            }
        )

    @property
    def schema(self):
        """The schema of the plugin

        Extends the super's schema
        """
        schema = super().schema
        schema['properties'].update(
            {
                'artist': {'type': 'string'},
                'album': {'type': 'string'},
                'year': {'type': ['string', 'integer']},
                'tags': one_or_more({'type': 'string'}),
                'tag_type': {'type': 'string', 'enum': list(self._opts('tag_type').keys())},
                'encoding': {'type': 'string', 'enum': self._opts('encoding')},
                'format': {'type': 'string', 'enum': self._opts('format')},
                'media': {'type': 'string', 'enum': self._opts('media')},
                'release_type': {
                    'type': 'string',
                    'enum': list(self._opts('release_type').keys()),
                },
                'log': {
                    'oneOf': [
                        {'type': 'string', 'enum': list(self._opts('log').keys())},
                        {'type': 'boolean'},
                    ]
                },
                'leech_type': {'type': 'string', 'enum': list(self._opts('leech_type').keys())},
                'hascue': {'type': 'boolean'},
                'scene': {'type': 'boolean'},
                'vanityhouse': {'type': 'boolean'},
            }
        )
        return schema

    def get_entries(self, search_results):
        """Generator that yields Entry objects from search results"""
        for result in search_results:
            # Get basic information on the release
            info = {k: result[k] for k in ('artist', 'groupName', 'groupYear')}

            # Releases can have multiple download options
            for tor in result['torrents']:
                temp = info.copy()
                temp.update({k: tor[k] for k in ('media', 'encoding', 'format', 'torrentId')})

                yield Entry(
                    title="{artist} - {groupName} - {groupYear} "
                    "({media} - {format} - {encoding})-{torrentId}.torrent".format(**temp),
                    url="{}/torrents.php?action=download&id={}&authkey={}&torrent_pass={}"
                    "".format(self.base_url, temp['torrentId'], self.authkey, self.passkey),
                    torrent_seeds=tor['seeders'],
                    torrent_leeches=tor['leechers'],
                    # Size is returned in bytes
                    content_size=parse_filesize(str(tor['size']) + "b"),
                )


class InputRedacted(InputGazelleMusic):
    """A plugin that searches RED"""

    def __init__(self):
        """Set up custom base_url and parameters"""
        super().__init__()
        self.base_url = "https://redacted.ch"

        self.params['encoding'].remove("q8.x (VBR)")
        self.params['format'].remove("Ogg Vorbis")
        self.params['media'].append("Blu-ray")
        self.params['releasetype'].update({"demo": 17, "concert recording": 18, "dj mix": 19})


class InputNotWhat(InputGazelleMusic):
    """A plugin that searches NWCD"""

    def __init__(self):
        """Set up custom base_url and parameters"""
        super().__init__()
        self.base_url = "https://notwhat.cd"

        self.params['media'].extend(['Blu-ray', 'Unknown'])
        self.params['releasetype'].update({'demo': 22, 'dj mix': 23, 'concert recording': 24})
        self.params['haslog'].update(
            {
                "gold": 102,
                "silver": 101,
                "gold/silver": 100,
                "lineage": -5,
                "unscored": -1,
                "missing lineage": -6,
                "missing dr score": -7,
                "missing sample rate": -8,
                "missing description": -9,
            }
        )


@event('plugin.register')
def register_plugin():
    plugin.register(InputGazelle, 'gazelle', interfaces=['task', 'search'], api_ver=2)
    plugin.register(InputGazelleMusic, 'gazellemusic', interfaces=['task', 'search'], api_ver=2)
    plugin.register(InputRedacted, 'redacted', interfaces=['task', 'search'], api_ver=2)
    plugin.register(InputNotWhat, 'notwhatcd', interfaces=['task', 'search'], api_ver=2)
