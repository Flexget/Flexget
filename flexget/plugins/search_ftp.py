import urllib
import logging
import os
import ftplib
import re
from urlparse import urlparse

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.search import normalize_unicode, clean_title

log = logging.getLogger('search_ftp')


class SearchFTP(object):
    """
        Search a file or a directory on a ftp
    """

    schema = {
        'type': 'object',
        'properties': {
            'ftp-url': {
                'oneOf': [
                    {'type': 'string'},
                    {'type': 'array', 'items': {'type': 'string'}},
                ],
            },
            'search-cmd': {'type': 'string', 'default': 'site search'},
            'match-regex': {'type': "string", 'format': 'regexp', 'default': '200- ([^ ]+) \([0-9]+F'},
            'search-append': {'type': 'string'},
            'replace-str': {'type': 'object'},
            'strip-chars': {'type': 'string', 'format': 'regexp', 'default': '[\',:]'},
        },
        'required': ['ftp-url'],
        'additionalProperties': False
    }

    def pepend_searchstring(self, config, search_string):
        if config['strip-chars']:
            search_string = re.sub(config['strip-chars'], '', search_string)
        if config.get('replace-str'):
            for tpl in config['replace-str'].keys():
                search_string = re.sub(tpl, config['replace-str'].get(tpl), search_string)
        if config['search-append']:
            search_string += ' ' + config['search-append']
        return search_string

    def ftp_connect(self, config, ftp_url):
        if re.search(':\+[1-9][0-9]*/?$', ftp_url, re.I):
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()
        ftp_url = urlparse(ftp_url)
        log.debug("Connecting to %s:%d" % (ftp_url.hostname, ftp_url.port))
        ftp.connect(ftp_url.hostname, ftp_url.port)
        ftp.login(ftp_url.username, ftp_url.password)
        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        return ftp

    def search(self, entry, config):
        entries = set()

        if isinstance(config['ftp-url'], str):
            config['ftp-url'] = [config['ftp-url']]

        for search_string in entry.get('search_strings', [entry['title']]):
            search_string = normalize_unicode(clean_title(search_string))
            search_string = self.pepend_searchstring(config, search_string)
            search_cmd = config['search-cmd'] + ' ' + search_string

            for ftp_url in config['ftp-url']:
                ftp = self.ftp_connect(config, ftp_url)
                for path in self.ftp_search(ftp, config['match-regex'], search_cmd):
                    url = re.sub('//+', '/', ftp_url+'/'+path)
                    entries.add(Entry(os.path.basename(path), url))
                ftp.quit()
        return entries

    def ftp_search(self, ftp, matchreg, search_cmd):
        log.info("Searching using command: " + search_cmd)
        response = ftp.sendcmd(search_cmd)

        foundEntries = set()
        for resline in response.split("\n"):
            match = re.search(matchreg, resline, re.I)
            if (match and len(match.groups()) > 0):
                repath = match.group(1).strip()
                foundEntries.add(repath)
        return foundEntries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchFTP, 'search_ftp', groups=['search'], api_ver=2)
