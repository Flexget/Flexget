from __future__ import unicode_literals, division, absolute_import
import logging
import hashlib

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('trakt_watchlist')


class TraktWatchlist(object):
    """Submit all accepted movies in your trakt.tv watchlist."""

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'}
        },
        'required': ['username', 'password', 'api_key'],
        'additionalProperties': False
    }

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        """Finds accepted movies and submits them to the user trakt watchlist."""
        # Change password to an SHA1 digest of the password
        config['password'] = hashlib.sha1(config['password']).hexdigest()
        found = {}
        for entry in task.accepted:
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
                found.setdefault('movies', {}).setdefault('movies', []).append(movie)
                log.debug('Submit %s to trakt.tv watchlist.' % entry['title'])

        if not found:
            log.debug('Nothing to submit to trakt.')
            return

        if task.options.test:
            log.info('Not submitting to trakt.tv because of test mode.')
            return

        # Submit our found items to trakt
        post_url = 'http://api.trakt.tv/movie/watchlist/' + config['api_key']
        for item in found.itervalues():
            # Add username and password to the dict to submit
            item.update({'username': config['username'], 'password': config['password']})
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
    plugin.register(TraktWatchlist, 'trakt_watchlist', api_ver=2)
