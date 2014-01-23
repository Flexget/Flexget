"""Plugin for plex media server (www.plexapp.com)."""
from xml.dom.minidom import parseString
import re
import logging
import os
from os.path import basename
from socket import gethostbyname
from string import find

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests

log = logging.getLogger('plex')


class InputPlex(object):
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
    'username'          Myplex (http://my.plexapp.com) username, used to connect to shared PMS'.
    'password'          Myplex (http://my.plexapp.com) password, used to connect to shared PMS'. 
    'server'            Host/IP of PMS to connect to. 
    'lowercase_title'   Convert filename (title) to lower case.
    'strip_year'        Remove year from title, ex: Show Name (2012) 01x01 => Show Name 01x01.
                        Movies will have year added to their filename unless this is set.
    'original_filename' Use filename stored in PMS instead of transformed name. lowercase_title and strip_year
                        will be ignored.
    'unwatched_only'    Request only unwatched media from PMS.
    'fetch'             What to download, can be set to the following values:
        - file          The file itself, default.
        - art           Series or movie art as configured in PMS
        - cover         Series cover for series, movie cover for movies.
        - thumb         Episode thumbnail, series only.
        - season_cover  Season cover, series only. If used in movies, movie cover will be set.


    Default paramaters:
      server           : localhost
      port             : 32400
      selection        : all
      lowercase_title  : no
      strip_year       : yes
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


    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='server')
        config.accept('text', key='selection')
        config.accept('integer', key='port')
        config.accept('text', key='section', required=True)
        config.accept('integer', key='section', required=True)
        config.accept('text', key='username')
        config.accept('text', key='password')
        config.accept('boolean', key='lowercase_title')
        config.accept('boolean', key='strip_year')
        config.accept('boolean', key='original_filename')
        config.accept('boolean', key='unwatched_only')
        config.accept('text', key='fetch')
        return config

    def prepare_config(self, config):
        config.setdefault('server', '127.0.0.1')
        config.setdefault('port', 32400)
        config.setdefault('selection', 'all')
        config.setdefault('username', '')
        config.setdefault('password', '')
        config.setdefault('lowercase_title', False)
        config.setdefault('strip_year', True)
        config.setdefault('original_filename', False)
        config.setdefault('unwatched_only', False)
        config.setdefault('fetch', 'file')
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        accesstoken = ""
        urlconfig = {}
        urlappend = "?"
        entries = []
        if config['unwatched_only'] and config['section'] != 'recentlyViewedShows' and config['section'] != 'all':
            urlconfig['unwatched'] = '1'
        plexserver = config['server']
        if gethostbyname(config['server']) != config['server']:
            config['server'] = gethostbyname(config['server'])
        if config['username'] and config['password'] and config['server'] != '127.0.0.1':
            header = {'X-Plex-Client-Identifier': 'flexget'}
            log.debug("Trying to to connect to myplex.")
            try:
                r = requests.post('https://my.plexapp.com/users/sign_in.xml',
                                  auth=(config['username'], config['password']), headers=header)
            except requests.RequestException as e:
                raise plugin.PluginError('Could not login to my.plexapp.com: %s. Username: %s Password: %s'
                                         % (e, config['username'], config['password']))
            log.debug("Connected to myplex.")
            if 'Invalid email' in r.text:
                raise plugin.PluginError("Could not login to my.plexapp.com: invalid username and/or password!")
            log.debug("Managed to login to myplex.")
            dom = parseString(r.text)
            plextoken = dom.getElementsByTagName('authentication-token')[0].firstChild.nodeValue
            log.debug("Got plextoken: %s" % plextoken)
            try:
                r = requests.get("https://my.plexapp.com/pms/servers?X-Plex-Token=%s" % plextoken)
            except requests.RequestException as e:
                raise plugin.PluginError("Could not get servers from my.plexapp.com using "
                                         "authentication-token: %s. (%s)" % (plextoken, e))
            dom = parseString(r.text)
            for node in dom.getElementsByTagName('Server'):
                if node.getAttribute('address') == config['server']:
                    accesstoken = node.getAttribute('accessToken')
                    log.debug("Got accesstoken: %s" % accesstoken)
                    urlconfig['X-Plex-Token'] = accesstoken
            if accesstoken == "":
                raise plugin.PluginError('Could not retrieve accesstoken for %s.' % config['server'])
        for key in urlconfig:
            urlappend += '%s=%s&' % (key, urlconfig[key])
        if not isinstance(config['section'], int):
            try:
                r = requests.get("http://%s:%d/library/sections/%s" %
                                 (config['server'], config['port'], urlappend))
            except requests.RequestException as e:
                raise plugin.PluginError('Error retrieving source: %s' % e)
            dom = parseString(r.text.encode("utf-8"))
            for node in dom.getElementsByTagName('Directory'):
                if node.getAttribute('title') == config['section']:
                    config['section'] = int(node.getAttribute('key'))
        if not isinstance(config['section'], int):
            raise plugin.PluginError('Could not find section \'%s\'' % config['section'])
        log.debug("Fetching http://%s:%d/library/sections/%s/%s%s" %
                  (config['server'], config['port'], config['section'], config['selection'], urlappend))
        try:
            r = requests.get("http://%s:%d/library/sections/%s/%s%s" %
                             (config['server'], config['port'], config['section'], config['selection'], urlappend))
        except requests.RequestException as e:
            raise plugin.PluginError('Error retrieving source: %s' % e)
        dom = parseString(r.text.encode("utf-8"))
        plexsectionname = dom.getElementsByTagName('MediaContainer')[0].getAttribute('title1')
        log.debug("Plex section name %s" % plexsectionname)
        if dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup') == "show":
            for node in dom.getElementsByTagName('Directory'):
                e = Entry()
                title = node.getAttribute('title')
                if config['strip_year']:
                    title = re.sub(r'^(.*)\(\d+\)$', r'\1', title)
                title = re.sub(r'[\(\)]', r'', title)
                title = re.sub(r'&', r'And', title)
                title = re.sub(r'[^A-Za-z0-9- ]', r'', title)
                if config['lowercase_title']:
                    title = title.lower()
                e['title'] = title
                e['url'] = "NULL"
                e['plex_server'] = plexserver
                e['plex_port'] = config['port']
                e['plex_section'] = config['section']
                e['plex_section_name'] = plexsectionname
                entries.append(e)
        elif dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup') == "episode":
            for node in dom.getElementsByTagName('Video'):
                e = Entry()
                title = node.getAttribute('grandparentTitle')
                season = int(node.getAttribute('parentIndex'))
                episodethumb = "http://%s:%d%s%s" % (config['server'], config['port'],
                                                     node.getAttribute('thumb'), urlappend)
                seriesart = "http://%s:%d%s%s" % (config['server'], config['port'],
                                                  node.getAttribute('art'), urlappend)
                seasoncover = "http://%s:%d%s%s" % (config['server'], config['port'],
                                                    node.getAttribute('parentThumb'), urlappend)
                seriescover = "http://%s:%d%s%s" % (config['server'], config['port'],
                                                    node.getAttribute('grandparentThumb'), urlappend)
                episodetitle = node.getAttribute('title')
                episodesummary = node.getAttribute('summary')
                count = node.getAttribute('viewCount')
                offset = node.getAttribute('viewOffset')
                if count:
                    status='seen'
                elif offset:
                    status = 'inprogress'
                else:
                    status = 'unwatched'

                if node.getAttribute('parentIndex') == node.getAttribute('year'):
                    season = node.getAttribute('originallyAvailableAt')
                    filenamemap = "%s_%s%s_%s_%s_%s.%s"
                    episode = ""
                elif node.getAttribute('index'):
                    episode = int(node.getAttribute('index'))
                    filenamemap = "%s_%02dx%02d_%s_%s_%s.%s"
                else:
                    log.debug("Could not get episode number for '%s' (Hint, ratingKey: %s)"
                              % (title, node.getAttribute('ratingKey')))
                    break
                for media in node.getElementsByTagName('Media'):
                    vcodec = media.getAttribute('videoCodec')
                    acodec = media.getAttribute('audioCodec')
                    if config['fetch'] == "file" or not config['fetch']:
                        container = media.getAttribute('container')
                    else:
                        container = "jpg"
                    resolution = media.getAttribute('videoResolution') + "p"
                    for part in media.getElementsByTagName('Part'):
                        key = part.getAttribute('key')
                        duration = part.getAttribute('duration')
                        if config['original_filename']:
                            filename, fileext = os.path.splitext(basename(part.getAttribute('file')))
                            if config['fetch'] != 'file':
                                filename += ".jpg"
                            else:
                                filename = "%s.%s" % (filename, fileext)
                        else:
                            title = re.sub(r'[\(\)]', r'', title)
                            title = re.sub(r'&', r'And', title).strip()
                            title = re.sub(r'[^A-Za-z0-9- _]', r'', title)
                            if config['strip_year']:
                                title = re.sub(r'^(.*)\(\d+\)$', r'\1', title)
                            if config['lowercase_title']:
                                title = title.lower()
                            filename = filenamemap % (title.replace(" ", "."), season, episode, resolution, vcodec,
                                                      acodec, container)
                        e['title'] = filename
                        e['filename'] = filename
                        e['plex_url'] = "http://%s:%d%s%s" % (config['server'], config['port'], key, urlappend)
                        e['url'] = "http://%s:%d%s%s" % (config['server'], config['port'], key, urlappend)
                        e['plex_server'] = plexserver
                        e['plex_server_ip'] = config['server']
                        e['plex_port'] = config['port']
                        e['plex_section'] = config['section']
                        e['plex_section_name'] = plexsectionname
                        e['plex_path'] = key
                        e['plex_duration'] = duration
                        e['plex_thumb'] = episodethumb
                        e['plex_art'] = seriesart
                        e['plex_cover'] = seriescover
                        e['plex_season_cover'] = seasoncover
                        e['plex_title'] = episodetitle
                        e['plex_summary'] = episodesummary
                        e['plex_status'] = status
                        if config['fetch'] == "file" or not config['fetch']:
                            e['url'] = e['plex_url']
                        elif config['fetch'] == "thumb":
                            e['url'] = e['plex_thumb']
                        elif config['fetch'] == "art":
                            e['url'] = e['plex_art']
                        elif config['fetch'] == "cover":
                            e['url'] = e['plex_cover']
                        elif config['fetch'] == "season_cover":
                            e['url'] = e['plex_season_cover']
                        log.debug("Setting url to %s since %s was selected." % (e['url'], config['fetch']))
                        if find(e['url'], '/library/') == -1:
                            log.debug('Seems like the chosen item could not be found in the PMS.')
                            break
                        entries.append(e)
        elif dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup') == "movie":
            if config['fetch'] == "thumb":
                raise plugin.pluginError('There are no thumbnails for movies.')
            for node in dom.getElementsByTagName('Video'):
                e = Entry()
                title = node.getAttribute('title')
                log.debug("found %s" % title)
                art = node.getAttribute('art')
                thumb = node.getAttribute('thumb')
                duration = node.getAttribute('duration')
                year = node.getAttribute('year')
                summary = node.getAttribute('summary')
                count = node.getAttribute('viewCount')
                offset = node.getAttribute('viewOffset')
                if count:
                    status='seen'
                elif offset:
                    status = 'inprogress'
                else:
                    status = 'unwatched'
                for media in node.getElementsByTagName('Media'):
                    vcodec = media.getAttribute('videoCodec')
                    acodec = media.getAttribute('audioCodec')
                    resolution = media.getAttribute('videoResolution') + 'p'
                    for part in media.getElementsByTagName('Part'):
                        key = part.getAttribute('key')
                        if config['fetch'] == "file" or not config['fetch']:
                            container = media.getAttribute('container')
                        else:
                            container = "jpg"
                        if config['original_filename']:
                            filename, fileext = os.path.splitext(basename(part.getAttribute('file')))
                            if config['fetch'] != 'file':
                                e['title'] = "%s.jpg" % filename
                            else:
                                e['title'] = "%s.%s" % (filename, fileext)
                        else:
                            title = re.sub(r'&', r'And', title).strip()
                            title = re.sub(r'[^A-Za-z0-9- _]', r'', title).replace(" ", ".")
                            if config['strip_year']:
                                filenamemap = "%s_%s_%s_%s.%s"
                                e['title'] = filenamemap % (title, resolution, vcodec, acodec, container)
                            else:
                                filenamemap = "%s_%d_%s_%s_%s.%s"
                                e['title'] = filenamemap % (title, year, resolution, vcodec, acodec, container)
                            if config['lowercase_title']:
                                title = title.lower()
                        e['filename'] = e['title']
                        e['plex_url'] = "http://%s:%d%s%s" % (config['server'], config['port'], key, urlappend)
                        e['url'] = "http://%s:%d%s%s" % (config['server'], config['port'], key, urlappend)
                        e['plex_server'] = plexserver
                        e['plex_server_ip'] = config['server']
                        e['plex_port'] = config['port']
                        e['plex_section'] = config['section']
                        e['plex_section_name'] = plexsectionname
                        e['plex_path'] = key
                        e['plex_duration'] = duration
                        e['plex_episode_thumb'] = ''
                        e['plex_art'] = art
                        e['plex_cover'] = thumb
                        e['plex_summary'] = summary
                        e['plex_title'] = title
                        e['plex_status'] = status
                        if config['fetch'] == "file" or not config['fetch']:
                            e['url'] = e['plex_url']
                        elif config['fetch'] == "cover" or config['fetch'] == "season_cover":
                            e['url'] = e['plex_cover']
                        elif config['fetch'] == "art":
                            e['url'] = e['plex_art']
                        if find(e['url'], '/library/') == -1:
                            log.debug('Seems like the chosen item could not be found in PMS, missing art?')
                            break
                        entries.append(e)
        else:
            raise plugin.PluginError('Selected section is neither TV nor movie section.')
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputPlex, 'plex', api_ver=2)
