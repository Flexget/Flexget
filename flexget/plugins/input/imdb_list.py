from __future__ import unicode_literals, division, absolute_import
import logging
import csv
import re
from cgi import parse_header

from flexget.utils import requests
from flexget.utils.imdb import make_url
from flexget.utils.cached_input import cached
from flexget.utils.tools import decode_html
from flexget.plugin import register_plugin, PluginError
from flexget.entry import Entry
from flexget.utils.soup import get_soup

log = logging.getLogger('imdb_list')

USER_ID_RE = r'^ur\d{7,8}$'


class ImdbList(object):
    """"Creates an entry for each movie in your imdb list."""

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'string',
                'pattern': USER_ID_RE,
                'error_pattern': 'user_id must be in the form urXXXXXXX'
            },
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'list': {'type': 'string'}
        },
        'required': ['list'],
        'additionalProperties': False
    }

    @cached('imdb_list', persist='2 hours')
    def on_task_input(self, task, config):
        sess = requests.Session()
        if config.get('username') and config.get('password'):

            log.verbose('Logging in ...')

            # Log in to imdb with our handler
            params = {'login': config['username'], 'password': config['password']}
            try:
                # First get the login page so we can get the hidden input value
                soup = get_soup(sess.get('https://secure.imdb.com/register-imdb/login').content)

                tag = soup.find('input', attrs={'name': '49e6c'})
                if tag:
                    params['49e6c'] = tag['value']
                else:
                    log.warning('Unable to find required info for imdb login, maybe their login method has changed.')
                # Now we do the actual login with appropriate parameters
                r = sess.post('https://secure.imdb.com/register-imdb/login', data=params, raise_status=False)
            except requests.RequestException as e:
                raise PluginError('Unable to login to imdb: %s' % e.message)

            # IMDb redirects us upon a successful login.
            # removed - doesn't happen always?
            # if r.status_code != 302:
            #     log.warning('It appears logging in to IMDb was unsuccessful.')

            # try to automatically figure out user_id from watchlist redirect url
            if not 'user_id' in config:
                log.verbose('Getting user_id ...')
                try:
                    response = sess.get('http://www.imdb.com/list/watchlist')
                except requests.RequestException as e:
                    log.error('Error retrieving user ID from imdb: %s' % e.message)
                    user_id = ''
                else:
                    log.debug('redirected to %s' % response.url)
                    user_id = response.url.split('/')[-2]
                if re.match(USER_ID_RE, user_id):
                    config['user_id'] = user_id
                else:
                    raise PluginError('Couldn\'t figure out user_id, please configure it manually.')

        if not 'user_id' in config:
            raise PluginError('Configuration option `user_id` required.')

        log.verbose('Retrieving list %s ...' % config['list'])

        # Get the imdb list in csv format
        try:
            url = 'http://www.imdb.com/list/export'
            params = {'list_id': config['list'], 'author_id': config['user_id']}
            log.debug('Requesting %s' % url)
            opener = sess.get(url, params=params)
            mime_type = parse_header(opener.headers['content-type'])[0]
            log.debug('mime_type: %s' % mime_type)
            if mime_type != 'text/csv':
                raise PluginError('Didn\'t get CSV export as response. Probably specified list `%s` does not exist.'
                                  % config['list'])
            csv_rows = csv.reader(opener.iter_lines())
        except requests.RequestException as e:
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
