"""Plugin for plex media server (www.plexapp.com)."""
from xml.dom.minidom import parse, parseString
import re
import logging
from flexget.utils import requests
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry
from socket import gethostbyname
from os.path import basename

log = logging.getLogger('plex')


class InputPlex(object):
    """
    Uses a plex media server (www.plexapp.com) tv section as an input.

    'section'           Required parameter, numerical (/library/sections/<num>) or section name.
    'selection'         Can be set to different keys:
        - all
        - unwatched
        - recentlyAdded
        - recentlyViewed
        - recentlyViewedShows
      'all' and 'recentlyViewedShows' will only produce a list of show names while the other three will produce 
      filename and download url.
    'username'          Myplex (http://my.plexapp.com) username, used to connect to shared PMS'.
    'password'          Myplex (http://my.plexapp.com) password, used to connect to shared PMS'. 
    'server'            Host/IP of PMS to connect to. 
    'lowercase_title'   Convert filename (title) to lower case.
    'strip_year'        Remove year from title, ex: Show Name (2012) 01x01 => Show Name 01x01
    'original_filename' Use filename stored in PMS instead of transformed name. lowercase_title and strip_year
                        will be ignored.
    'unwatched_only'    Request only unwatched media from PMS.

    Default paramaters:
      server           : localhost
      port             : 32400
      selection        : all
      lowercase_title  : no
      strip_year       : yes
      original_filename: no
      unwatched_only   : no

    Example:

      plex:
        server: 192.168.1.23
        section: 3
        selection: recentlyAdded
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
        return config

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        accesstoken = ""
        urlconfig = {}
        urlappend = "?"
        if (config['unwatched_only'] and config['section'] != 'recentlyViewedShows' 
            and config['section'] != 'all'):
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
                raise PluginError('Could not login to my.plexapp.com: %s. Username: %s Password: %s' 
                    % (e, config['username'], config['password']))
            log.debug("Managed to connect to myplex.")
            if 'Invalid email' in r.text:
                raise PluginError('Could not login to my.plexapp.com: invalid username and/or password!')
            log.debug("Managed to login to myplex.")
            dom = parseString(r.text)
            plextoken = dom.getElementsByTagName('authentication-token')[0].firstChild.nodeValue
            log.debug("Got plextoken: %s" % plextoken)
            try:
                r = requests.get("https://my.plexapp.com/pms/servers?X-Plex-Token=%s" % plextoken)
            except requests.RequestException as e:
                raise PluginError('Could not get servers from my.plexapp.com using authentication-token: %s.' 
                    % plextoken)
            dom = parseString(r.text)
            for node in dom.getElementsByTagName('Server'):
                if node.getAttribute('address') == config['server']:
                    accesstoken = node.getAttribute('accessToken') 
                    log.debug("Got accesstoken: %s" % accesstoken)
                    urlconfig['X-Plex-Token'] = accesstoken
            if accesstoken == "":
                raise PluginError('Could not retrieve accesstoken for %s.' % config['server'])
        for key in urlconfig:
            urlappend += '%s=%s&' % (key, urlconfig[key])
        if not isinstance(config['section'], int):
            try:
                r = requests.get("http://%s:%d/library/sections/%s" % 
                    (config['server'], config['port'], urlappend))
            except requests.RequestException as e:
                raise PluginError('Error retrieving source: %s' % e)
            dom = parseString(r.text.encode("utf-8"))
            for node in dom.getElementsByTagName('Directory'):
                if node.getAttribute('title') == config['section']:
                    config['section'] = int(node.getAttribute('key'))
        if not isinstance(config['section'], int):
            raise PluginError('Could not find section \'%s\'' % config['section'])
        log.debug("Fetching http://%s:%d/library/sections/%s/%s%s" %
            (config['server'], config['port'], config['section'], config['selection'], urlappend))
        try:
            r = requests.get("http://%s:%d/library/sections/%s/%s%s" % 
                (config['server'], config['port'], config['section'], config['selection'], urlappend))
        except requests.RequestException as e:
            raise PluginError('Error retrieving source: %s' % e)
        dom = parseString(r.text.encode("utf-8"))
        entries = []
        plexsectionname = dom.getElementsByTagName('MediaContainer')[0].getAttribute('title1')
        if dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup') == "show":
            for node in dom.getElementsByTagName('Directory'):
                title = node.getAttribute('title')
                if config['strip_year']:
                    title = re.sub(r'^(.*)\(\d+\)$', r'\1', title)
                title = re.sub(r'[\(\)]', r'', title)
                title = re.sub(r'\&', r'And', title)
                title = re.sub(r'[^A-Za-z0-9- ]', r'', title)
                if config['lowercase_title']:
                    title = title.lower()
                e = Entry()
                e['title'] = title
                e['url'] = "NULL"
                e['plex_server'] = plexserver
                e['plex_port'] = config['port']
                e['plex_section'] = config['section']
                e['plex_section_name'] = plexsectionname
                entries.append(e)
        elif dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup') == "episode":
            for node in dom.getElementsByTagName('Video'):
                title = node.getAttribute('grandparentTitle')
                season = int(node.getAttribute('parentIndex'))
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
                    container = media.getAttribute('container')
                    resolution = media.getAttribute('videoResolution') + "p"
                    for part in media.getElementsByTagName('Part'):
                        key = part.getAttribute('key')
                        e = Entry()
                        if config['original_filename']:
                            e['title'] = basename(part.getAttribute('file'))
                        else:
                            if config['strip_year']:
                                title = re.sub(r'^(.*)\(\d+\)$', r'\1', title)
                            title = re.sub(r'[\(\)]', r'', title)
                            title = re.sub(r'\&', r'And', title).strip()
                            title = re.sub(r'[^A-Za-z0-9- ]', r'', title).replace(" ", ".")
                            if config['lowercase_title']:
                                title = title.lower()
                            e['title'] = filenamemap % (title, season, episode, resolution, vcodec, acodec, container) 
                        e['url'] = "http://%s:%d%s%s" % (config['server'], config['port'], key, urlappend)
                        e['plex_server'] = plexserver
                        e['plex_server_ip'] = config['server']
                        e['plex_port'] = config['port']
                        e['plex_section'] = config['section']
                        e['plex_section_name'] = plexsectionname
                        e['plex_path'] = key
                        entries.append(e)
        else:
            raise PluginError('Selected section is not a TV section.')
        return entries

register_plugin(InputPlex, 'plex', api_ver=2)
