import logging
import csv
import re
import urllib
import urllib2
from functools import partial
from flexget.utils.imdb import make_url
from flexget.utils.cached_input import cached
from flexget.utils.tools import urlopener as _urlopener, decode_html
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry

log = logging.getLogger('imdb_list')

USER_ID_RE = r'^ur\d{7,8}$'


class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('regexp_match', key='user_id').\
             accept(USER_ID_RE, message='user_id must be in the form urXXXXXXX')
        root.accept('text', key='username')
        root.accept('text', key='password')
        root.accept('text', key='list', required=True)
        return root

    @cached('imdb_list', persist='2 hours')
    def on_feed_input(self, feed, config):
        urlopener = partial(_urlopener, log=log, retries=2)
        if config.get('username') and config.get('password'):
            # Create a cookie handler, make sure it is used in our calls to urlopener
            cookiehandler = urllib2.HTTPCookieProcessor()
            urlopener = partial(urlopener, handlers=[cookiehandler])

            log.verbose('Logging in ...')

            # Log in to imdb with our handler
            params = urllib.urlencode({'login': config['username'], 'password': config['password']})
            try:
                urlopener('https://secure.imdb.com/register-imdb/login', data=params)
            except urllib2.URLError, e:
                raise PluginError('Unable to login to imdb: %s' % e.message)

            # try to automatically figure out user_id from watchlist redirect url
            if not 'user_id' in config:
                log.verbose('Getting user_id ...')
                opener = urlopener('http://www.imdb.com/list/watchlist')
                redirected = opener.geturl()
                log.debug('redirected to %s' % redirected)
                user_id = redirected.split('/')[-2]
                if re.match(USER_ID_RE, user_id):
                    config['user_id'] = user_id
                else:
                    raise PluginError('Couldn\'t figure out user_id, please configure it manually.')

        if not 'user_id' in config:
            raise PluginError('Configuration option `user_id` required.')

        log.verbose('Retrieving list %s ...' % config['list'])

        # Get the imdb list in csv format
        try:
            url = 'http://www.imdb.com/list/export?list_id=%s&author_id=%s' % (config['list'], config['user_id'])
            log.debug('Requesting %s' % url)
            opener = urlopener(url)
            mime_type = opener.headers.gettype()
            log.debug('mime_type: %s' % mime_type)
            if mime_type != 'text/csv':
                raise PluginError('Didn\'t get CSV export as response. Probably specified list `%s` does not exists.'
                    % config['list'])
            csv_rows = csv.reader(opener)
        except urllib2.URLError, e:
            raise PluginError('Unable to get imdb list: %s' % e.message)

        # Create an Entry for each movie in the list
        entries = []
        for row in csv_rows:
            if not row or row[0] == 'position':
                # Don't use blank rows or the headings row
                continue
            try:
                title = decode_html(row[5]).decode('utf-8')
                entries.append(Entry(title=title, url=make_url(row[1]), imdb_id=row[1], imdb_name=title))
            except IndexError:
                log.critical('IndexError! Unable to handle row: %s' % row)
        return entries


register_plugin(ImdbList, 'imdb_list', api_ver=2)
