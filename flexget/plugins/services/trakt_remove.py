from __future__ import unicode_literals, division, absolute_import
import logging
import hashlib

from requests import RequestException

from flexget.plugin import register_plugin
from flexget.utils import json

log = logging.getLogger('trakt_remove')


class TraktRemove(object):
    """Remove all accepted movies from your trakt.tv library."""

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['movies']},
            'list': {'type': 'string'}
        },
        'required': ['username', 'password', 'api_key', 'type', 'list'],
        'additionalProperties': False
    }

    def on_task_exit(self, task, config):
        """Finds accepted movies and series episodes and submits them to trakt as acquired."""
        # Change password to an SHA1 digest of the password
        config['password'] = hashlib.sha1(config['password']).hexdigest()

        # Don't edit the config, or it won't pass validation on rerun
        url_params = config.copy()
        url_params['data_type'] = 'list'
        # Do some translation from visible list name to prepare for use in url
        list_name = config['list'].lower()
        # These characters are just stripped in the url
        for char in '!@#$%^*()[]{}/=?+\\|-_':
            list_name = list_name.replace(char, '')
        # These characters get replaced
        list_name = list_name.replace('&', 'and')
        list_name = list_name.replace(' ', '-')
        url_params['list_type'] = list_name
        # Map type is per item in custom lists
        
        found = {}
        for entry in task.accepted:
            # if config['type'] == 'series':
                # # Check entry is a series episode
                # if entry.get('series_name') and entry.get('series_id_type') == 'ep':
                    # series = found.setdefault(entry['series_name'], {})
                    # if not series:
                        # # If this is the first episode found from this series, set the parameters
                        # series['title'] = entry.get('tvdb_series_name', entry['series_name'])
                        # if entry.get('imdb_id'):
                            # series['imdb_id'] = entry['imdb_id']
                        # if entry.get('tvdb_id'):
                            # series['tvdb_id'] = entry['tvdb_id']
                        # series['episodes'] = []
                    # episode = {'season': entry['series_season'], 'episode': entry['series_episode']}
                    # series['episodes'].append(episode)
                    # log.debug('Marking %s S%02dE%02d for submission to trakt.tv library.' %
                              # (entry['series_name'], entry['series_season'], entry['series_episode']))
            if config['type'] == 'movies':
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
                    # We use an extra container dict so that the found dict is usable in the same way as found series
                    if url_params['list'] == 'watchlist': 
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
         
        # URL to remove collected entries from trakt list    
        if url_params['list'] == 'watchlist':          
            post_url = 'http://api.trakt.tv/movie/unwatchlist/' + config['api_key']
        else:
            post_url = 'http://api.trakt.tv/lists/items/delete/' + config['api_key']
                
        # Delete entry from list    
        for item in found.itervalues():
            # Add username, password and list (slug) to the dict to submit
            item.update({'username': config['username'], 'password': config['password'], 'slug': url_params['list']})
            try:
                result = task.requests.post(post_url, data=json.dumps(item), raise_status=False)
            except RequestException as e:
                log.error('Error submitting data to trakt.tv: %s' % e)
                continue

            if result.status_code == 404:
                # Remove some info from posted json and print the rest to aid debugging
                for key in ['username', 'password', 'episodes']:
                    item.pop(key, None)
                log.warning('%s not found on trakt (remove_collected): %s' % (config['type'].capitalize(), item))
                continue
            elif result.status_code == 401:
                log.error('Error authenticating with trakt (remove_collected). Check your username/password/api_key')
                log.debug(result.text)
                continue
            elif result.status_code != 200:
                log.error('Error submitting data to trakt.tv (remove_collected): %s' % result.text)
                continue
            # log.debug(result.text)
            
register_plugin(TraktRemove, 'trakt_remove', api_ver=2)
