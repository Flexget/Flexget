"""Plugin for plex media server (www.plexapp.com)."""
import os
import re
from datetime import datetime
from os.path import basename
from socket import gethostbyname
from xml.dom.minidom import parseString

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests

logger = logger.bind(name='plex')


class InputPlex:
    """
    Uses a plex media server (www.plexapp.com) tv section as an input.

    'section'           Required parameter, numerical (/library/sections/<num>) or section name.
    'selection'         Can be set to different keys:
        - all                   : Default
        - unwatched             :
        - recentlyAdded         :
        - recentlyViewed        :
        - recentlyViewedShows   : Series only.
      'all' and 'recentlyViewedShows' will only produce a list of show names while the other three will produce
      filename and download url.
    'token'             Plex access token, used to connect to PMS
    'username'          Myplex (http://my.plexapp.com) username, used to connect to shared PMS'.
    'password'          Myplex (http://my.plexapp.com) password, used to connect to shared PMS'.
    'server'            Host/IP of PMS to connect to.
    'lowercase_title'   Convert filename (title) to lower case.
    'strip_non_alpha'   Sanitize filename (title), stripping all non-alphanumeric letters.
                        Better to turn off in case of non-english titles.
    'strip_year'        Remove year from title, ex: Show Name (2012) 01x01 => Show Name 01x01.
                        Movies will have year added to their filename unless this is set.
    'strip_parens'      Remove information in parens from title, ex: Show Name (UK)(2012) 01x01 => Show Name 01x01.
    'original_filename' Use filename stored in PMS instead of transformed name. lowercase_title and strip_year
                        will be ignored.
    'unwatched_only'    Request only unwatched media from PMS.
    'fetch'             What to download, can be set to the following values:
        - file          The file itself, default.
        - art           Series or movie art as configured in PMS
        - cover         Series cover for series, movie cover for movies.
        - thumb         Episode thumbnail, series only.
        - season_cover  Season cover, series only. If used in movies, movie cover will be set.


    Default parameters:
      server           : localhost
      port             : 32400
      selection        : all
      lowercase_title  : no
      strip_non_alpha  : yes
      strip_year       : yes
      strip_parens     : no
      original_filename: no
      unwatched_only   : no
      fetch            : file

    Example:

      plex:
        server: 192.168.1.23
        section: 3
        selection: recentlyAdded
        fetch: series_art
    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string', 'default': '127.0.0.1'},
            'port': {'type': 'integer', 'default': 32400},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'token': {'type': 'string'},
            'section': {'type': ['string', 'integer']},
            'selection': {'type': 'string', 'default': 'all'},
            'lowercase_title': {'type': 'boolean', 'default': False},
            'strip_non_alpha': {'type': 'boolean', 'default': True},
            'strip_year': {'type': 'boolean', 'default': True},
            'strip_parens': {'type': 'boolean', 'default': False},
            'original_filename': {'type': 'boolean', 'default': False},
            'unwatched_only': {'type': 'boolean', 'default': False},
            'fetch': {
                'type': 'string',
                'default': 'file',
                'enum': ['file', 'art', 'cover', 'thumb', 'season_cover'],
            },
        },
        'required': ['section'],
        'not': {
            'anyOf': [{'required': ['token', 'username']}, {'required': ['token', 'password']}]
        },
        'error_not': 'Cannot specify `username` and `password` with `token`',
        'dependencies': {'username': ['password'], 'password': ['username']},
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        config['plexserver'] = config['server']
        config = self.plex_format_server(config)
        return config

    def plex_get_globalaccesstoken(self, config):
        header = {'X-Plex-Client-Identifier': 'flexget'}
        try:
            r = requests.post(
                'https://my.plexapp.com/users/sign_in.xml',
                auth=(config['username'], config['password']),
                headers=header,
            )
        except requests.RequestException as error:
            raise plugin.PluginError('Could not log in to myplex! Error: %s' % error)
        if 'Invalid email' in r.text:
            raise plugin.PluginError('Myplex: invalid username and/or password!')
        dom = parseString(r.text)
        globalaccesstoken = dom.getElementsByTagName('authentication-token')[
            0
        ].firstChild.nodeValue
        if not globalaccesstoken:
            raise plugin.PluginError('Myplex: could not find a server!')
        else:
            logger.debug('Myplex: Got global accesstoken: {}', globalaccesstoken)
        return globalaccesstoken

    def plex_get_accesstoken(self, config, globalaccesstoken=""):
        accesstoken = None
        if not globalaccesstoken:
            globalaccesstoken = self.plex_get_globalaccesstoken(config)
        if config['server'] in ('localhost', '127.0.0.1'):
            logger.debug('Server using localhost. Global Token will be used')
            return globalaccesstoken
        try:
            r = requests.get(
                "https://my.plexapp.com/pms/servers?X-Plex-Token=%s" % globalaccesstoken
            )
        except requests.RequestException as e:
            raise plugin.PluginError(
                "Could not get servers from my.plexapp.com using "
                f"authentication-token: {globalaccesstoken}. ({e})"
            )
        dom = parseString(r.text)
        for node in dom.getElementsByTagName('Server'):
            if config['server'] in (
                node.getAttribute('address'),
                node.getAttribute('localAddresses'),
            ):
                accesstoken = node.getAttribute('accessToken')
                logger.debug('Got plextoken: {}', accesstoken)
        if not accesstoken:
            raise plugin.PluginError('Could not retrieve accesstoken for %s.' % config['server'])
        else:
            return accesstoken

    def plex_format_server(self, config):
        if gethostbyname(config['server']) != config['server']:
            config['server'] = gethostbyname(config['server'])
        return config

    def plex_section_is_int(self, section):
        return isinstance(section, int)

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        urlconfig = {}
        urlappend = "?"
        entries = []
        if (
            config['unwatched_only']
            and config['section'] != 'recentlyViewedShows'
            and config['section'] != 'all'
        ):
            urlconfig['unwatched'] = '1'
        if config.get('token'):
            accesstoken = config['token']
            logger.debug('Using accesstoken: {}', accesstoken)
            urlconfig['X-Plex-Token'] = accesstoken
        elif config.get('username'):
            accesstoken = self.plex_get_accesstoken(config)
            logger.debug('Got accesstoken: {}', accesstoken)
            urlconfig['X-Plex-Token'] = accesstoken

        for key in urlconfig:
            urlappend += f'{key}={urlconfig[key]}&'
        if not self.plex_section_is_int(config['section']):
            try:
                path = "/library/sections/"
                r = requests.get(
                    "http://%s:%d%s%s" % (config['plexserver'], config['port'], path, urlappend)
                )
            except requests.RequestException as e:
                raise plugin.PluginError('Error retrieving source: %s' % e)
            dom = parseString(r.text.encode("utf-8"))
            for node in dom.getElementsByTagName('Directory'):
                if node.getAttribute('title') == config['section']:
                    config['section'] = int(node.getAttribute('key'))
        if not self.plex_section_is_int(config['section']):
            raise plugin.PluginError('Could not find section \'%s\'' % config['section'])

        logger.debug(
            'Fetching http://{}:{}/library/sections/{}/{}{}',
            config['server'],
            config['port'],
            config['section'],
            config['selection'],
            urlappend,
        )
        try:
            path = "/library/sections/{}/{}".format(config['section'], config['selection'])
            r = requests.get(
                "http://%s:%d%s%s" % (config['plexserver'], config['port'], path, urlappend)
            )
        except requests.RequestException as e:
            raise plugin.PluginError(
                'There is no section with number %d. (%s)' % (config['section'], e)
            )
        dom = parseString(r.text.encode("utf-8"))
        plexsectionname = dom.getElementsByTagName('MediaContainer')[0].getAttribute('title1')
        viewgroup = dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup')

        logger.debug('Plex section "{}" is a "{}" section', plexsectionname, viewgroup)
        if viewgroup != "movie" and viewgroup != "show" and viewgroup != "episode":
            raise plugin.PluginError("Section is neither a movie nor tv show section!")
        domroot = "Directory"
        titletag = "title"
        if viewgroup == "episode":
            domroot = "Video"
            titletag = "grandparentTitle"
            thumbtag = "thumb"
            arttag = "art"
            seasoncovertag = "parentThumb"
            covertag = "grandparentThumb"
        elif viewgroup == "movie":
            domroot = "Video"
            titletag = "title"
            arttag = "art"
            seasoncovertag = "thumb"
            covertag = "thumb"
            if config['fetch'] == "thumb":
                raise plugin.PluginError(
                    "Movie sections does not have any thumbnails to download!"
                )
        for node in dom.getElementsByTagName(domroot):
            e = Entry()
            e['plex_server'] = config['plexserver']
            e['plex_port'] = config['port']
            e['plex_section'] = config['section']
            e['plex_section_name'] = plexsectionname
            e['plex_episode_thumb'] = ''

            title = node.getAttribute(titletag)
            if config['strip_year']:
                title = re.sub(r'^(.*)\(\d{4}\)(.*)', r'\1\2', title)
            if config['strip_parens']:
                title = re.sub(r'\(.*?\)', r'', title)
                title = title.strip()
            if config['strip_non_alpha']:
                title = re.sub(r'[\(\)]', r'', title)
                title = re.sub(r'&', r'And', title)
                title = re.sub(r'[^A-Za-z0-9- \']', r'', title)
            if config['lowercase_title']:
                title = title.lower()
            if viewgroup == "show":
                e['title'] = title
                e['url'] = 'NULL'
                entries.append(e)
                # show ends here.
                continue
            e['plex_art'] = "http://%s:%d%s%s" % (
                config['server'],
                config['port'],
                node.getAttribute(arttag),
                urlappend,
            )
            e['plex_cover'] = "http://%s:%d%s%s" % (
                config['server'],
                config['port'],
                node.getAttribute(covertag),
                urlappend,
            )
            e['plex_season_cover'] = "http://%s:%d%s%s" % (
                config['server'],
                config['port'],
                node.getAttribute(seasoncovertag),
                urlappend,
            )
            if viewgroup == "episode":
                e['plex_thumb'] = "http://%s:%d%s%s" % (
                    config['server'],
                    config['port'],
                    node.getAttribute('thumb'),
                    urlappend,
                )
                e['series_name'] = title
                e['plex_ep_name'] = node.getAttribute('title')
                season = int(node.getAttribute('parentIndex'))
                if node.getAttribute('parentIndex') == node.getAttribute('year'):
                    season = node.getAttribute('originallyAvailableAt')
                    filenamemap = "%s_%s%s_%s_%s_%s.%s"
                    episode = ""
                    e['series_id_type'] = 'date'
                    e['series_date'] = season
                elif node.getAttribute('index'):
                    episode = int(node.getAttribute('index'))
                    filenamemap = "%s_%02dx%02d_%s_%s_%s.%s"
                    e['series_season'] = season
                    e['series_episode'] = episode
                    e['series_id_type'] = 'ep'
                    e['series_id'] = 'S%02dE%02d' % (season, episode)
                else:
                    logger.debug(
                        "Could not get episode number for '{}' (Hint, ratingKey: {})",
                        title,
                        node.getAttribute('ratingKey'),
                    )
                    break
            elif viewgroup == "movie":
                filenamemap = "%s_%s_%s_%s.%s"

            e['plex_year'] = node.getAttribute('year')
            e['plex_added'] = datetime.fromtimestamp(int(node.getAttribute('addedAt')))
            e['plex_duration'] = node.getAttribute('duration')
            e['plex_summary'] = node.getAttribute('summary')
            e['plex_userrating'] = node.getAttribute('userrating')
            e['plex_key'] = node.getAttribute('ratingKey')
            count = node.getAttribute('viewCount')
            offset = node.getAttribute('viewOffset')
            if count:
                e['plex_status'] = "seen"
            elif offset:
                e['plex_status'] = "inprogress"
            else:
                e['plex_status'] = "unwatched"
            for media in node.getElementsByTagName('Media'):
                entry = Entry(e)
                vcodec = media.getAttribute('videoCodec')
                acodec = media.getAttribute('audioCodec')
                if media.hasAttribute('title'):
                    entry['plex_media_title'] = media.getAttribute('title')
                if media.hasAttribute('optimizedForStreaming'):
                    entry['plex_stream_optimized'] = media.getAttribute('optimizedForStreaming')
                if config['fetch'] == "file" or not config['fetch']:
                    container = media.getAttribute('container')
                else:
                    container = "jpg"
                resolution = media.getAttribute('videoResolution') + "p"
                for part in media.getElementsByTagName('Part'):
                    if config['fetch'] == "file" or not config['fetch']:
                        key = part.getAttribute('key')
                    elif config['fetch'] == "art":
                        key = node.getAttribute(arttag)
                    elif config['fetch'] == "cover":
                        key = node.getAttribute(arttag)
                    elif config['fetch'] == "season_cover":
                        key = node.getAttribute(seasoncovertag)
                    elif config['fetch'] == "thumb":
                        key = node.getAttribute(thumbtag)
                    # key = part.getAttribute('key')
                    duration = part.getAttribute('duration')
                    entry['plex_title'] = title
                    entry['title'] = title
                    if config['original_filename']:
                        filename, fileext = os.path.splitext(basename(part.getAttribute('file')))
                        if config['fetch'] != 'file':
                            filename += ".jpg"
                        else:
                            filename = f"{filename}{fileext}"
                    else:
                        if viewgroup == "episode":
                            filename = filenamemap % (
                                title.replace(" ", "."),
                                season,
                                episode,
                                resolution,
                                vcodec,
                                acodec,
                                container,
                            )
                            entry['title'] = filename
                        elif viewgroup == "movie":
                            filename = filenamemap % (
                                title.replace(" ", "."),
                                resolution,
                                vcodec,
                                acodec,
                                container,
                            )
                            entry['title'] = filename
                    entry['plex_url'] = "http://%s:%d%s%s" % (
                        config['server'],
                        config['port'],
                        key,
                        urlappend,
                    )
                    entry['plex_path'] = key
                    entry['url'] = "http://%s:%d%s%s" % (
                        config['server'],
                        config['port'],
                        key,
                        urlappend,
                    )
                    entry['plex_duration'] = duration
                    entry['filename'] = filename
                    if key == "":
                        logger.debug("Could not find anything in PMS to download. Next!")
                    else:
                        entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputPlex, 'plex', api_ver=2)
