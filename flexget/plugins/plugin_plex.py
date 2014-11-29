import re
from xml.dom.minidom import parseString
from os.path import basename, splitext
import logging
from socket import gethostbyname
from string import find
from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import requests


def getAccessToken(username, password, header = ""):
    if not header:
        header = "python"
    header = {'X-Plex-Client-Identifier': '%s' % header}
    try:
        r = requests.post('https://my.plexapp.com/users/sign_in.xml', auth=(username, password), headers = header)
    except requests.RequestException as e:
        return e
    if 'Invalid email' in r.text:
        return ""
    dom = parseString(r.text)
    accesstoken = dom.getElementsByTagName('authentication-token')[0].firstChild.nodeValue
    return accesstoken

def getSharedServers(accesstoken):
    try:
        r = requests.get("https://my.plexapp.com/pms/servers?X-Plex-Token=%s" % accesstoken)
    except requests.RequestException as e:
        return e
    if 'Invalid' in r.text:
        return ""

    dom = parseString(r.text)
    data = []
    for server in dom.getElementsByTagName('MediaContainer')[0].getElementsByTagName('Server'):
        if not int(server.getAttribute('owned')):
            data.append({'name': server.getAttribute('name'),
                         'address': server.getAttribute('address'),
                         'port': int(server.getAttribute('port')),
                         'host': server.getAttribute('host'),
                         'identifier': server.getAttribute('machineIdentifier'),
                         'accesstoken': server.getAttribute('accessToken'),
                         'source': server.getAttribute('sourceTitle'),
                         'owned': int(server.getAttribute('owned'))})
    return data

def getOwnServers(accesstoken):
    try:
        r = requests.get("https://my.plexapp.com/pms/servers?X-Plex-Token=%s" % accesstoken)
    except requests.RequestException as e:
        return e
    if 'Invalid' in r.text:
        return ""
    dom = parseString(r.text)
    data = []
    for server in dom.getElementsByTagName('MediaContainer')[0].getElementsByTagName('Server'):
        if int(server.getAttribute('owned')):
            data.append({'name': server.getAttribute('name'),
                         'address': server.getAttribute('address'),
                         'port': int(server.getAttribute('port')),
                         'host': server.getAttribute('host'),
                         'identifier': server.getAttribute('machineIdentifier'),
                         'accesstoken': server.getAttribute('accessToken'),
                         'source': server.getAttribute('sourceTitle'),
                         'owned': int(server.getAttribute('owned'))})
    return data

def getAllSections(accesstoken, includeown = 0):
    data = []
    for server in getSharedServers(accesstoken):
        for section in getSections(server):
            data.append(dict(server, **section))
    if includeown:
        for server in getOwnServers(accesstoken):
            for section in getSections(server):
                data.append(dict(server, **section))
    return data

def getAllSectionsByType(type, accesstoken, includeown = 0):
    data = []
    for server in getSharedServers(accesstoken):
        for section in getSectionsByType(type, server):
            data.append(dict(server, **section))
    if includeown:
        for server in getOwnServers(accesstoken):
            for section in getSectionsByType(type, server):
                data.append(dict(server, **section))
    return data



def getSections(host, port="", accesstoken=""):
    data = []
    if isinstance(host, dict):
        port = host['port']
        accesstoken = host['accesstoken']
        remotehost = host['host']
    else:
        remotehost = host
    try:
        r = requests.get("http://%s:%d/library/sections?X-Plex-Token=%s" % (remotehost, port, accesstoken))
    except requests.RequestException as e:
        return e
    if 'Invalid' in r.text:
        return ""

    dom = parseString(r.text)
    for directory in dom.getElementsByTagName('MediaContainer')[0].getElementsByTagName('Directory'):
        data.append({'name': directory.getAttribute('title'),
                     'key': int(directory.getAttribute('key')),
                     'type': directory.getAttribute('type'),
                     'scanner': directory.getAttribute('scanner'),
                     'updated': directory.getAttribute('updatedAt')})
    return data

def getServerByName(name, accesstoken):
    for server in getSharedServers(accesstoken):
        if name == server['name']:
            return server

def getServerByUser (user, accesstoken):
    for server in getSharedServers(accesstoken):
        if user == server['source']:
            return server

def getSectionsByType(type, host, port = "", accesstoken = "" ):
    data = []
    if isinstance(host, dict):
        sections = getSections(host)
    else:
        sections = getSections(host, port, accesstoken)
    for section in sections:
        if section['type'] == type:
            data.append(section)
    return data

def listSection(section, host, selection = "all", port = "", accesstoken = ""):
    data = []
    title = ""
    file = ""
    size = int()
    filename = ""
    duration = ""
    art = ""
    thumb = ""
    cover = ""
    season_cover = ""
    summary = ""
    videocodec = ""
    audiocodec = ""
    videoresolution = ""
    domroot = "Directory"
    titletag = "title"
    thumbtag = "thumb"
    arttag = "art"
    seasoncovertag = ""
    covertag = ""
    cover = ""
    season_cover = ""
    seasonnumber = int()
    episodenumber = int()

    if isinstance(host, dict):
        remotehost = host['host']
        port = host['port']
        accesstoken = host['accesstoken']
    else:
        remotehost = host

    try:
        r = requests.get("http://%s:%d/library/sections/%d/%s?X-Plex-Token=%s" % (remotehost, port, section, selection,
                                                                           accesstoken))
#        print ("http://%s:%d/library/sections/%d/%s?X-Plex-Token=%s" % (remotehost, port, section, selection,
#                                                                                   accesstoken))
    except requests.RequestException as e:
        return e
    if 'Invalid' in r.text:
        return ""

    dom = parseString(r.text.encode("utf-8"))
    type = dom.getElementsByTagName('MediaContainer')[0].getAttribute('viewGroup')
    if type == "secondary" and len(dom.getElementsByTagName('MediaContainer')[0].childNodes) != 1:
        type = dom.getElementsByTagName('MediaContainer')[0].getElementsByTagName('Video')[0].getAttribute('type')
    if type == "movie":
        domroot = "Video"
        titletag = "title"
        arttag = "art"
        seasoncovertag = "thumb"
        covertag = "thumb"
        thumbtag = "thumb"
    elif type == "episode":
        domroot = "Video"
        titletag = "grandparentTitle"
        thumbtag = "thumb"
        arttag = "art"
        seasoncovertag = "parentThumb"
        covertag = "grandparentThumb"
    for node in dom.getElementsByTagName(domroot):
        title = node.getAttribute(titletag)
        if title == "*yearBreak*":
            continue
        key = node.getAttribute('ratingKey')
        summary = node.getAttribute('summary')
        art = node.getAttribute(arttag)
        cover = node.getAttribute(covertag)
        season_cover = node.getAttribute(seasoncovertag)
        thumb = node.getAttribute(thumbtag)
        viewcount = node.getAttribute('viewCount')
        duration = node.getAttribute('duration')

        seasonnumber = node.getAttribute('parentIndex')
        episodenumber = node.getAttribute('index')
        if seasonnumber:
            seasonnumber = int(seasonnumber)
        else:
            seasonnumber = int()
        if episodenumber:
            episodenumber = int(episodenumber)
        else:
            episodenumber = int()
        year = node.getAttribute('year')
        if type == "show":
            data.append({'title': title,
                          'file': file,
                          'size': size,
                          'filename': filename,
                          'duration': duration,
                          'season': seasonnumber,
                          'episode': episodenumber,
                          'viewcount': viewcount,
                          'art': art,
                          'thumb': thumb,
                          'cover': cover,
                          'season_cover': season_cover,
                          'summary': summary,
                          'videocodec': videocodec,
                          'audiocodec': audiocodec,
                          'videoresolution': videoresolution,
                          'url': "http://%s:%d/library/metadata/%s/allLeaves?X-Plex-Token=%s" %
                                 (remotehost,port,key,accesstoken),
                          'host': remotehost,
                          'port': port,
                          'key': key,
                          'accesstoken': accesstoken
                          })

            continue
        if type != "show":
            for media in node.getElementsByTagName('Media'):
                videocodec = media.getAttribute('videoCodec')
                audiocodec = media.getAttribute('audioCodec')
                videoresolution = media.getAttribute('videoResolution')

                if re.sub('[^0-9]', '', videoresolution):
                    videoresolution += 'p'
                for part in media.getElementsByTagName('Part'):
                    file = part.getAttribute('key')
                    size = int(part.getAttribute('size'))
                    filename = basename(part.getAttribute('file'))
                    container = part.getAttribute('container')
                    if not filename:
                        if type == "movie":
                            filename = "%s_%s.%s" % (title.replace(" ", "."), year, container)
                        elif type == "episode":
                            filename = "%s_S%02dxE%02d.%s" % (title.replace(" ", "."),
                                                              seasonnumber, episodenumber, container)
                    data.append({'title': title,
                                 'file': file,
                                 'size': size,
                                 'filename': filename,
                                 'duration': duration,
                                 'season': seasonnumber,
                                 'episode': episodenumber,
                                 'art': art,
                                 'thumb': thumb,
                                 'cover': cover,
                                 'season_cover': season_cover,
                                 'summary': summary,
                                 'videocodec': videocodec,
                                 'audiocodec': audiocodec,
                                 'videoresolution': videoresolution,
                                 'url': "http://%s:%d%s?X-Plex-Token=%s" % (remotehost,port,file,accesstoken),
                                 'host': remotehost,
                                 'port': port,
                                 'key': key,
                                 'accesstoken': accesstoken
                                 })
    return data



class InputPlex(object):
    schema = {
        'properties': {
            'username': {'type': 'string'},
            'password:': {'type': 'string'},
            'server': {'type': 'string'},
            'section': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]},
            'sectiontype': {'type': 'string'},
            'myplex': {'type': 'array', 'items':{
                'oneOf': [{'username': 'string'},
                          {'servername': 'string'},
                    {'allservers': 'enum'}]}}
        }
    }
#
#http://address-of-plex-machine:32400/library/sections/3/refresh
#http://address-of-plex-machine:32400/library/sections/3/refresh?deep=1
#http://address-of-plex-machine:32400/library/sections/3/refresh?force=1


@event('plugin.register')
def register_plugin():
    plugin.register(InputPlex, 'plex', api_ver=2)
    plugin.register(PlexOutput, 'plex_
