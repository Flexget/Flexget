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

    All parameters except `username` and `password` are optional.

    whatcd:
        username:
        password:

        user_agent: (A custom user-agent for the client to report.
                     It is NOT A GOOD IDEA to spoof a browser with
                     this. You are responsible for your account.)

        search: (general search filter)

        artist: (artist name)
        album: (album name)
        year: (album year)

        encoding: (encoding specifics - 192, 320, lossless, etc.)
        format: (MP3, FLAC, AAC, etc.)
        media: (CD, DVD, vinyl, Blu-ray, etc.)
        release_type: (album, soundtrack, EP, etc.)

        log: (log specification - true, false, '100%', or '<100%')
        hascue: (has a cue file - true or false)
        scene: (is a scene release - true or false)
        vanityhouse: (is a vanity house release - true or false)
        leech_type: ('freeleech', 'neutral', 'either', or 'normal')

        tags: (a list of tags to match - drum.and.bass, new.age, blues, etc.)
        tag_type: (match 'any' or 'all' of the items in `tags`)
    """

    # Aliases for config -> api params
    ALIASES = {
        "artist": "artistname",
        "album": "groupname",
        "leech_type": "freetorrent",
        "release_type": "releaseType",
        "tags": "taglist",
        "tag_type": "tags_type",
        "search": "searchstr",
        "log": "haslog",
    }

    # API parameters
    # None means a raw value entry (no validation)
    # A dict means a choice with a mapping for the API
    # A list is just a choice with no mapping
    PARAMS = {
        "searchstr": None,
        "taglist": None,
        "artistname": None,
        "groupname": None,
        "year": None,
        "tags_type": {
            "any": 0,
            "all": 1,
        },
        "encoding": [
            "192", "APS (VBR)", "V2 (VBR)", "V1 (VBR)", "256", "APX (VBR)",
            "V0 (VBR)", "320", "lossless", "24bit lossless", "V8 (VBR)"
        ],
        "format": [
            "MP3", "FLAC", "AAC", "AC3", "DTS"
        ],
        "media": [
            "CD", "DVD", "vinyl", "soundboard", "SACD", "DAT", "cassette",
            "WEB", "Blu-ray"
        ],
        "releaseType": {
            "album": 1,
            "soundtrack": 3,
            "EP": 5,
            "anthology": 6,
            "compilation": 7,
            "DJ mix": 8,
            "single": 9,
            "live album": 11,
            "remix": 13,
            "bootleg": 14,
            "interview": 15,
            "mixtape": 16,
            "unknown": 21,
            "concert recording": 22,
            "demo": 23
        },
        "haslog": {
            "False": 0,
            "True": 1,
            "100%": 100,
            "<100%": -1
        },
        "freetorrent": {
            "freeleech": 1,
            "neutral": 2,
            "either": 3,
            "normal": 0,
        },
        "hascue": {
            "False": 0,
            "True": 1,
        },
        "scene": {
            "False": 0,
            "True": 1,
        },
        "vanityhouse": {
            "False": 0,
            "True": 1,
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
            if isinstance(val, list):
                return ",".join(val)
            return val
        elif isinstance(opts, dict):
            # Options, translate the input to output
            # The str cast converts bools to 'True'/'False' for use as keys
            return opts[str(val)]
        else:
            # List of options, check it's in the list
            if val not in opts:
                return None
            return val

    def __init__(self):
        """Set up the schema"""

        self.schema = {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'password': {'type': 'string'},
                'user_agent': {'type': 'string'},
                'search': {'type': 'string'},
                'artist': {'type': 'string'},
                'album': {'type': 'string'},
                'year': {'type': ['string', 'integer']},
                'tags': one_or_more({'type': 'string'}),
                'tag_type': {'type': 'string', 'enum': self._opts('tag_type').keys()},
                'encoding': {'type': 'string', 'enum': self._opts('encoding')},
                'format': {'type': 'string', 'enum': self._opts('format')},
                'media': {'type': 'string', 'enum': self._opts('media')},
                'release_type': {'type': 'string', 'enum': self._opts('release_type').keys()},
                'log': {'oneOf': [{'type': 'string', 'enum': self._opts('log').keys()}, {'type': 'boolean'}]},
                'leech_type': {'type': 'string', 'enum': self._opts('leech_type').keys()},
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

        r = self.session.post("https://ssl.what.cd/login.php", data=data,
                              allow_redirects=False)
        if r.status_code != 302 or r.headers.get('location') != "index.php":
            raise PluginError("Failed to log in to What.cd")

        accountinfo = self._request("index")

        self.authkey = accountinfo["authkey"]
        self.passkey = accountinfo["passkey"]
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
            key = self._key(k)
            if key is not None:
                params[key] = self._getval(k, v)

        # Params other than the searching ones
        params['action'] = action
        if 'page' in kwargs:
            params['page'] = kwargs['page']

        r = self.session.get(ajaxpage, params=params, allow_redirects=False)
        if r.status_code != 200:
            raise PluginError("What.cd returned a non-200 status code")

        try:
            json_response = r.json()
            if json_response['status'] != "success":

                # Try to deal with errors returned by the API
                error = json_response.get('error', json_response.get('status'))
                if not error or error == "failure":
                    error = json_response.get('response')
                if not error:
                    error = str(json_response)

                raise PluginError("What.cd gave a failure response: "
                                  "'{0}'".format(error))
            return json_response['response']
        except (ValueError, TypeError, KeyError) as e:
            raise PluginError("What.cd returned an invalid response")

    @cached('whatcd')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        """Search on What.cd"""

        self.session = Session()
        user_agent = config.get('user_agent')
        if user_agent:
            # Using a custom user agent
            self.session.headers.update({"User-Agent": user_agent})

        # From the API docs: "Refrain from making more than five (5) requests every ten (10) seconds"
        self.session.set_domain_delay('ssl.what.cd', '2 seconds')

        # Login
        self._login(config)

        # Perform the query
        results = []
        page = 1
        while True:
            result = self._request("browse", page=page, **config)
            if not result['results']:
                break
            results.extend(result["results"])
            pages = result['pages']
            page = result['currentPage']
            log.info("Got {0} of {1} pages".format(page, pages))
            if page >= pages:
                break
            page += 1

        # Logged in and made a request successfully, it's ok if nothing matches
        task.no_entries_ok = True

        # Parse the needed information out of the response
        entries = []
        for result in results:
            # Get basic information on the release
            info = dict((k, result[k]) for k in ('artist', 'groupName', 'groupYear'))

            # Releases can have multiple download options
            for tor in result['torrents']:
                temp = info.copy()
                temp.update(dict((k, tor[k]) for k in ('media', 'encoding', 'format', 'torrentId')))

                entries.append(Entry(
                    title="{artist} - {groupName} - {groupYear} "
                          "({media} - {format} - {encoding})-{torrentId}.torrent".format(**temp),
                    url="https://what.cd/torrents.php?action=download&"
                        "id={0}&authkey={1}&torrent_pass={2}".format(temp['torrentId'], self.authkey, self.passkey),
                    torrent_seeds=tor['seeders'],
                    torrent_leeches=tor['leechers'],
                    # Size is given in bytes, convert it
                    content_size=int(tor['size'] / (1024**2) * 100) / 100
                ))

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputWhatCD, 'whatcd', groups=['search'], api_ver=2)
