from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.cached_input import cached
from flexget.utils.requests import Session

log = logging.getLogger('whatcd')

class InputWhatCD(object):
    """A plugin that searches what.cd

    == Usage:

    whatcd:
        username:
        password:

        [other optional params]
    """

    # Aliases for config -> api params
    ALIASES = {
        "artist": "artistname",
        "album": "groupname",
        "leech_type": "freetorrent",
        "release_type": "releasetype",
        "tags": "tag_list",
        "tag_type": "tags_type",
    }

    # API parameters
    # None means a raw value entry (no validation)
    # A dict means a choice with a mapping for the API
    # A list is just a choice with no mapping
    PARAMS = {
        "taglist": None,
        "artistname": None,
        "groupname": None,
        "year": None,
        "hascue": None,
        "scene": None,
        "vanityhouse": None,
        "tags_type": {
            "any": 0,
            "all": 1,
        },
        "encoding": [
            "192", "APS (VBR)", "V2 (VBR)", "V1 (VBR)", "256", "APX (VBR)",
            "V0 (VBR)", "320", "Lossless", "24bit Lossless", "V8 (VBR)"
        ],
        "format": [
            "MP3", "FLAC", "AAC", "AC3", "DTS"
        ],
        "media": [
            "CD", "DVD", "Vinyl", "Soundboard", "SACD", "DAT", "Cassette",
            "WEB", "Blu-ray"
        ],
        "releasetype": {
            "Album": 1,
            "Soundtrack": 3,
            "EP": 5,
            "Anthology": 6,
            "Compilation": 7,
            "DJ Mix": 8,
            "Single": 9,
            "Live Album": 11,
            "Remix": 13,
            "Bootleg": 14,
            "Interview": 15,
            "Mixtape": 16,
            "Unknown": 21,
            "Concert Recording": 22,
            "Demo": 23
        },
        "haslog": {
            "0": 0,
            "1": 1,
            "100%": 100,
            "<100%": -1
        },
        "freetorrent": {
            "freeleech": 1,
            "neutral": 2,
            "either": 3,
            "normal": 0,
        }
    }

    def _key(self, key):
        """Gets the API key name from the entered key"""
        try:
            if key in self.ALIASES:
                return self.ALIASES[key]
            elif key in self.PARAMS:
                return key
            return None
        except KeyError:
            return None

    def _opts(self, key):
        """Gets the options for the specified key"""
        temp = self._key(key)
        try:
            return self.PARAMS[temp]
        except KeyError:
            return None

    def _getval(self, key, val):
        """Gets the value for the specified key"""
        # No alias or param by that name
        if self._key(key) is None:
            return None

        opts = self._opts(key)
        if opts is None:
            # No options, use value passed in
            return val
        elif isinstance(opts, list):
            # List of options, check it's in it
            if val not in opts:
                return None
            return val
        else:
            # Options, translate the input to output
            return opts[val]

    def __init__(self):
        """Set up the schema"""

        self.schema = {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'password': {'type': 'string'},
                'artist': {'type': 'string'},
                'album': {'type': 'string'},
                'year': {'type': 'string'},
                'tags': one_or_more({'type': 'string'}),
                'tag_type': {'type': 'string', 'enum': self._opts('tag_type')},
                'encoding': {'type': 'string', 'enum': self._opts('encoding')},
                'format': {'type': 'string', 'enum': self._opts('format')},
                'media': {'type': 'string', 'enum': self._opts('media')},
                'release_type': {'type': 'string', 'enum': self._opts('release_type')},
                'haslog': {'type': 'string', 'enum': self._opts('haslog')},
                'leech_type': {'type': 'string', 'enum': self._opts('leech_type')},
                'hascue': {'type': 'boolean'},
                'scene': {'type': 'boolean'},
                'vanityhouse': {'type': 'boolean'},
            },
            'required': ['username', 'password'],
            'additionalProperties': False
        }

    def _login(self, config):
        """
        Log in and store auth data from the server
        Adapted from https://github.com/isaaczafuta/whatapi
        """

        data = {
            'username': config['username'],
            'password': config['password'],
            'keeplogged': 1,
        }

        r = self.session.post("https://ssl.what.cd/login.php", data=data, headers={"User-Agent": "Flexget-whatcd plugin"}, allow_redirects=False)
        if r.status_code != 302:
            raise PluginError("Failed to log in to What.cd")

        accountinfo = self._request("index")
        if not accountinfo:
            raise PluginError("Failed to get auth keys after logging in")

        self.authkey = accountinfo["response"]["authkey"]
        self.passkey = accountinfo["response"]["passkey"]
        log.info("Logged in to What.cd")

    def _request(self, action, **kwargs):
        """
        Make an AJAX request to a given action page
        Adapted from https://github.com/isaaczafuta/whatapi
        """

        ajaxpage = 'https://ssl.what.cd/ajax.php'

        params = {}

        # Filter params and map config values -> api values
        for k, v in kwargs.iteritems():
            k = self._key(k)
            if k is not None:
                params[k] = self._getval(k, v)

        params['action'] = action

        r = self.session.get(ajaxpage, params=params, allow_redirects=False)
        if r.status_code != 200:
            raise PluginError("Request to What.cd returned a non-200 status code")

        try:
            json_response = r.json()
            if json_response['status'] != "success":
                raise PluginError("What.cd gave a 'failure' response: '{0}'".format(json_response['error']))
            return json_response
        except (ValueError, TypeError) as e:
            raise PluginError("What.cd returned an invalid response")

    @cached('whatcd')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        """Search on What.cd"""

        self.session = Session()

        # Login
        self._login(config)

        # Perform the query
        # TODO: pagination
        results = self._request("browse", **config)
        log.debug(results)

        # TODO: Parse results into Entry objects
        #FORMAT = https://what.cd/torrents.php?action=download&id={id}&authkey={authkey}&torrent_pass={passkey}

        #entry = Entry()
        #entry['title'] = "title"
        #entry['url'] = "url"
        #entry['content_size'] = 0

        return []

@event('plugin.register')
def register_plugin():
    plugin.register(InputWhatCD, 'whatcd', groups=['search'], api_ver=2)
