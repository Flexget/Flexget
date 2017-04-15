from __future__ import unicode_literals, division, absolute_import
import logging
import hashlib

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('trakt_add')


class TraktAdd(object):
    """Submit all accepted movies in your trakt.tv watchlist/library/seen or custom list."""

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'},
            'list': {'type': 'string'}
        },
        'required': ['username', 'password', 'api_key', 'list'],
        'additionalProperties': False
    }

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        """Finds accepted movies and submits them to the user trakt watchlist."""
        # Change password to an SHA1 digest of the password
        config['password'] = hashlib.sha1(config['password']).hexdigest()

        # Don't edit the config, or it won't pass validation on rerun
        url_params = config.copy()
        url_params['data_type'] = 'list'
        # Do some translation from visible list name to prepare for use in url
        list_name = config['list'].lower()
        # These characters are just stripped in the url
        for char in '!@#$%^*()[]{}/=?+\\|_':
            list_name = list_name.replace(char, '')
        # These characters get replaced
        list_name = list_name.replace('&', 'and')
        list_name = list_name.replace(' ', '-')
        url_params['list_type'] = list_name
        # Map type is per item in custom lists
        std_list = list_name in ['watchlist', 'seen', 'library']
        
        found = {}
        for entry in task.accepted:
            # Check entry is a movie
            if entry.get('imdb_id') or entry.get('tmdb_id'):
                movie = {}
                # We know imdb_id or tmdb_id is filled in, so don't cause any more lazy lookups
                if entry.get('movie_name', eval_lazy=False):
                    movie['title'] = entry['movie_name']
                if entry.get('movie_year', eval_lazy=False):
                    movie['year'] = entry['movie_year']
                if entry.get('tmdb_id', eval_lazy=False):
                    movie['tmdb_id'] = entry['tmdb_id']
                if entry.get('imdb_id', eval_lazy=False):
                    movie['imdb_id'] = entry['imdb_id']
                # the structure for custom lists is slightly different
                if std_list: 
                    found.setdefault('movies', {}).setdefault('movies', []).append(movie)
                else:          
                    movie['type'] = 'movie'          
                    found.setdefault('items', {}).setdefault('items', []).append(movie)
                log.debug('Marking %s for submission to trakt.tv library.' % entry['title'])
                # log.verbose('json dump (found) : %s' % json.dumps(found))

        if not found:
            log.debug('Nothing to submit to trakt.')
            return

        if task.manager.options.test:
            log.info('Not submitting to trakt.tv because of test mode.')
            return
         
        # URL to mark collected entries on trakt.tv    
        if std_list:
            post_url = 'http://api.trakt.tv/movie/%s/%s' % (list_name, config['api_key'])
        else:
            post_url = 'http://api.trakt.tv/lists/items/add/' + config['api_key']
        
        # Submit our found items to trakt
        for item in found.itervalues():
            # Add username and password to the dict to submit
            item.update({'username': config['username'], 'password': config['password'],
                         'slug': url_params['list_type']})
            try:
                result = task.requests.post(post_url, data=json.dumps(item), raise_status=False)
            except RequestException as e:
                log.error('Error submitting data to trakt.tv: %s' % e)
                continue

            if result.status_code == 404:
                # Remove some info from posted json and print the rest to aid debugging
                for key in ['username', 'password', 'episodes']:
                    item.pop(key, None)
                log.warning('%s not found on trakt: %s' % (config['type'].capitalize(), item))
                continue
            elif result.status_code == 401:
                log.error('Error authenticating with trakt. Check your username/password/api_key')
                log.debug(result.text)
                continue
            elif result.status_code != 200:
                log.error('Error submitting data to trakt.tv: %s' % result.text)
                continue


@event('plugin.register')
def register_plugin():
    plugin.register(TraktAdd, 'trakt_add', api_ver=2)
