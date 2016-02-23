from __future__ import unicode_literals, division, absolute_import
import logging
import re
from collections import MutableSet

from flexget.utils.requests import Session
from flexget.utils.soup import get_soup


log = logging.getLogger('imdb_list')
USER_ID_RE = r'^ur\d{7,8}$'
CUSTOM_LIST_RE = r'^ls\d{7,10}$'
USER_LISTS = ['watchlist', 'ratings', 'checkins']


class ImdbEntrySet(MutableSet):
    schema = {
        'type': 'object',
        'properties': {
            'login': {'type': 'string'},
            'password': {'type': 'string'},
            'list': {'type': 'string'},
            'force_language': {'type': 'string', 'default': 'en-us'}
        },
        'additionalProperties': False,
        'required': ['login', 'password', 'list']
    }
    def __init__(self, config):
        self.config = config
        self.session = Session()
        self.session.headers = {'Accept-Language': config.get('force_language', 'en-us')}
        self.user_id = None
        self.list_id = None
        self.authenticate()

    def authenticate(self):
        """Authenticates a session with imdb, and grabs any IDs needed for getting/modifying list."""
        r = self.session.get('https://www.imdb.com/ap/signin?openid.return_to=https%3A%2F%2Fwww.imdb.com%2Fap-signin-h'
                             'andler&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&op'
                             'enid.assoc_handle=imdb_mobile_us&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%'
                             '2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.'
                             'net%2Fauth%2F2.0')
        soup = get_soup(r.content)
        inputs = soup.select('form#ap_signin_form input')
        data = dict((i['name'], i.get('value')) for i in inputs if i.get('name'))
        data['email'] = self.config['login']
        data['password'] = self.config['password']
        self.session.post('https://www.imdb.com/ap/signin', data=data)
        # Get user id by exctracting from redirect url
        r = self.session.get('http://www.imdb.com/list/ratings', allow_redirects=False)
        self.user_id = re.search('ur\d+(?!\d)', r.headers['location']).group()
        # Get list ID
        if self.config['list'] == 'watchlist':
            data = {'consts[]': 'tt0805570', 'tracking_tag': 'watchlistRibbon'}
            wl_data = self.session.post('http://www.imdb.com/list/_ajax/watchlist_has', data=data).json()
            self.list_id = wl_data['list_id']
        else:
            self.list_id = self.config['list']

    def __contains__(self, x):
        pass

    def __iter__(self):
        pass

    def discard(self, entry):
        if 'imdb_id' not in entry:
            log.warning('Cannot remove %s from imdb_list because it does not have an imdb_id', entry['title'])
            return
        # Get the list item id
        item_ids = None
        if self.config['list'] == 'watchlist':
            data = {'consts[]': entry['imdb_id'], 'tracking_tag': 'watchlistRibbon'}
            status = self.session.post('http://www.imdb.com/list/_ajax/watchlist_has', data=data).json()
            item_ids = status.get('has', {}).get(entry['imdb_id'])
        else:
            data = {'tconst': entry['imdb_id']}
            status = self.session.post('http://www.imdb.com/list/_ajax/wlb_dropdown', data=data).json()
            for a_list in status['items']:
                if a_list['data_list_id'] == self.list_id:
                    item_ids = a_list['data_list_item_ids']
                    break
        if not item_ids:
            log.warning('%s is not in list %s, cannot be removed', entry['imdb_id'], self.list_id)
            return
        data = {
            'action': 'delete',
            'list_id': self.list_id,
            'ref_tag': 'title'
        }
        for item_id in item_ids:
            self.session.post('http://www.imdb.com/list/_ajax/edit', data=dict(data, list_item_id=item_id))

    def add(self, entry):
        if 'imdb_id' not in entry:
            log.warning('Cannot add %s to imdb_list because it does not have an imdb_id', entry['title'])
            return
        data = {
            'const': entry['imdb_id'],
            'list_id': self.list_id,
            'ref_tag': 'title'
        }
        self.session.post('http://www.imdb.com/list/_ajax/edit', data=data)

    def __len__(self):
        pass
