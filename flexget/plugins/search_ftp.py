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

    """ Search a file or a directory on a ftp

    == Options
      = url
        List of ftp-urls to use in the search-process.
        The url should be in the following syntax: ftp://user:pass@ftp.address.com:[+]22
        To use a ssl-connection against the ftp add the plus-sign to the port.

        This is the only option that is required.
      = search_append
        If specified, appends a string to the search-string supplied by the input-plugin.
        For example, if 'x264' is specified as 'search_append' and 'Riddick' is the output of
        the input-plugin the final search-string would be 'Riddick x264'.
      = replace
        Defines a map with strings to replace in the search-string.
        For example if replace is set to {'&': 'and', ' ': '.'}, all '&'-signs would be
        replaced with the word 'and' and all spaces would be replaced with dots.
      = strip_chars
        A regular expression whose matches will be completly removed from the search-string.
        The intention of this setting were to remove unwanted characters but any regex can be set.
        It defaults to '[\',:]'.
      = search_cmd
        Defines the raw command that should be used to search.
        Defaults to 'site search'
      = match_regex
        Defines the regular expression used to match hits. The expression is matched against the
        output given when issuing the raw search command.

    == Basic usage
      my-search-task:
        discover:
               - ... (e.g. emit_movie_queue)
        from:
            - search_ftp:
                url:
                  - "ftp://flexuser:flexpass@127.0.0.1:+13546"
                search_append: 'x264'
                replace: {'&': 'and'}
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {
                'oneOf': [
                    {'type': 'string'},
                    {'type': 'array', 'items': {'type': 'string'}},
                ],
            },
            'search_cmd': {'type': 'string', 'default': 'site search'},
            'match_regex': {'type': "string", 'format': 'regexp', 'default': '200- ([^ ]+) \([0-9]+F'},
            'search_append': {'type': 'string'},
            'replace': {'type': 'object'},
            'strip_chars': {'type': 'string', 'format': 'regexp', 'default': '[\',:]'},
        },
        'required': ['url'],
        'additionalProperties': False
    }

    def pepend_searchstring(self, config, search_string):
        if config['strip_chars']:
            search_string = re.sub(config['strip_chars'], '', search_string)
        if config.get('replace'):
            for tpl in config['replace'].keys():
                search_string = re.sub(tpl, config['replace'].get(tpl), search_string)
        if config['search_append']:
            search_string += ' ' + config['search_append']
        return search_string

    def ftp_connect(self, config, ftp_url):
        if re.search(':\+[1-9][0-9]*/?$', ftp_url, re.I):
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()
        ftp_url = urlparse(ftp_url)
        log.info("Connecting to %s:%d" % (ftp_url.hostname, ftp_url.port))
        ftp.connect(ftp_url.hostname, ftp_url.port)
        ftp.login(ftp_url.username, ftp_url.password)
        ftp.sendcmd('TYPE I')
        ftp.set_pasv(True)
        return ftp

    def search(self, entry, config):
        entries = set()

        if isinstance(config['url'], str):
            config['url'] = [config['url']]

        for ftp_url in config['url']:
            try:
                ftp = self.ftp_connect(config, ftp_url)
            except ftplib.all_errors as e:
                log.error('Failed connection attempt to %s: %s', ftp_url, str(e))
                continue

            for search_string in entry.get('search_strings', [entry['title']]):
                # setup search string
                search_string = normalize_unicode(clean_title(search_string))
                search_string = self.pepend_searchstring(config, search_string)
                search_cmd = config['search_cmd'] + ' ' + search_string

                for path in self.ftp_search(ftp, config['match_regex'], search_cmd):
                    log.info('Found title %s', os.path.basename(path))
                    url = ftp_url.rstrip('/') + '/' + path
                    entries.add(Entry(os.path.basename(path), url))
                ftp.quit()
        return entries

    def ftp_search(self, ftp, matchreg, search_cmd):
        log.debug("Searching using command: %s", search_cmd)
        response = ftp.sendcmd(search_cmd)

        found_entries = set()
        for resline in response.split("\n"):
            log.debug('RESPONSE: %s', resline)
            match = re.search(matchreg, resline, re.I)
            if (match and len(match.groups()) > 0):
                repath = match.group(1).strip()
                found_entries.add(repath)
        return found_entries


@event('plugin.register')
def register_plugin():
    plugin.register(SearchFTP, 'search_ftp', groups=['search'], api_ver=2)
