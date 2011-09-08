import logging
import csv
import urllib
import urllib2
from functools import partial
from flexget.utils.imdb import make_url
from flexget.utils.tools import urlopener as _urlopener, decode_html
from flexget.plugin import register_plugin, PluginError
from flexget.feed import Entry

log = logging.getLogger('imdb_list')


class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('regexp_match', key='user_id', required=True).\
            accept('^ur\d{7,8}$', message='user_id must be in the form urXXXXXXX')
        root.accept('text', key='username')
        root.accept('text', key='password')
        root.accept('text', key='list', required=True)
        return root

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

        log.verbose('Retrieving list %s ...' % config['list'])

        # Get the imdb list in csv format
        try:
            imdblist = csv.reader(urlopener('http://www.imdb.com/list/export?list_id=%s&author_id=%s' %
                                            (config['list'], config['user_id'])))
        except urllib2.URLError, e:
            raise PluginError('Unable to get imdb list: %s' % e.message)

        # Create an Entry for each movie in the list
        entries = []
        for row in imdblist:
            if not row or row[0] == 'position':
                # Don't use blank rows or the headings row
                continue
            title = decode_html(row[5])
            entries.append(Entry(title=title, url=make_url(row[1]), imdb_id=row[1], imdb_name=title))
        return entries


register_plugin(ImdbList, 'imdb_list', api_ver=2)
