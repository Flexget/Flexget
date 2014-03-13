from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget import validator
from flexget.entry import Entry
from flexget.event import event
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
    # None signifies a raw value entry, a dict means a choice
    # TODO: Lists for choices with no mapping (encoding, format, media)
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
        "encoding": {
            "192" : "192",
            "APS (VBR)" : "APS (VBR)",
            "V2 (VBR)": "V2 (VBR)",
            "V1 (VBR)": "V1 (VBR)",
            "256": "256",
            "APX (VBR)": "APX (VBR)",
            "V0 (VBR)": "V0 (VBR)",
            "320": "320",
            "Lossless": "Lossless",
            "24bit Lossless": "24bit Lossless",
            "V8 (VBR)": "V8 (VBR)"
        },
        "format": {
            "MP3": "MP3",
            "FLAC": "FLAC",
            "AAC": "AAC",
            "AC3": "AC3",
            "DTS": "DTS",
        },
        "media": {
            "CD": "CD",
            "DVD": "DVD",
            "Vinyl": "Vinyl",
            "Soundboard": "Soundboard",
            "SACD": "SACD",
            "DAT": "DAT",
            "Cassette": "Cassette",
            "WEB": "WEB",
            "Blu-ray": "Blu-ray"
        },
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
        try:
            if key in self.ALIASES:
                return self.PARAMS[self.ALIASES[key]]
            return self.PARAMS[key]
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
        else:
            # Options, translate the input to output
            return opts[val]

    # TODO: Do this with a schema property instead
    def validator(self):
        """Return config validator."""
        root = validator.factory('dict')
        root.accept('text', key='username', required=True)
        root.accept('text', key='password', required=True)

        root.accept('text', key='artist')
        root.accept('text', key='album')
        root.accept('text', key='year')
        root.accept('list', key='tags')

        root.accept('choice', key='tag_type').accept_choices(self._opts('tag_type'))
        root.accept('choice', key='encoding').accept_choices(self._opts('encoding'))
        root.accept('choice', key='format').accept_choices(self._opts('format'))
        root.accept('choice', key='media').accept_choices(self._opts('media'))
        root.accept('choice', key='release_type').accept_choices(self._opts('release_type'))
        root.accept('choice', key='haslog').accept_choices(self._opts('haslog'))
        root.accept('choice', key='leech_type').accept_choices(self._opts('leech_type'))

        root.accept('boolean', key="hascue")
        root.accept('boolean', key="scene")
        root.accept('boolean', key="vanityhouse")

        return root

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
            return False

        accountinfo = self._request("index")
        if not accountinfo:
            return False

        self.authkey = accountinfo["response"]["authkey"]
        self.passkey = accountinfo["response"]["passkey"]
        log.info("Logged in to What.cd")
        return True

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
            return None

        try:
            json_response = r.json()
            if json_response['status'] != "success":
                log.error("What.cd gave a 'failure' response: '{0}'".format(json_response['error']))
                return None
            return json_response
        except (ValueError, TypeError) as e:
            log.error("What.cd returned an invalid response")
            return None

    @cached('whatcd')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        """Search on What.cd"""

        self.session = Session()

        # Login
        if not self._login(config):
            log.error("Failed to log in to What.cd")
            return

        # Perform the query
        # TODO: pagination
        results = self._request("browse", **config)
        if results is not None:
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
