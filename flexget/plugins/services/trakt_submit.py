from __future__ import unicode_literals, division, absolute_import
import logging
import hashlib

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json


class TraktSubmit(object):

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

    # Defined by subclasses
    remove = None
    log = None

    def submit_data(self, task, url, params):
        if task.manager.options.test:
            self.log.info('Not submitting to trakt.tv because of test mode.')
            return
        prm = json.dumps(params)
        self.log.debug('Submitting data to trakt.tv (%s): %s' % (url, prm))
        try:
            result = task.requests.post(url, data=prm, raise_status=False)
        except RequestException as e:
            self.log.error('Error submitting data to trakt.tv: %s' % e)
            return
        if result.status_code == 404:
            # Remove some info from posted json and print the rest to aid debugging
            for key in ['username', 'password', 'episodes']:
                params.pop(key, None)
            self.log.warning('Some movie/show is unknown to trakt.tv: %s' % params)
        elif result.status_code == 401:
            self.log.error('Authentication error: check your trakt.tv username/password/api_key')
            self.log.debug(result.text)
        elif result.status_code != 200:
            self.log.error('Error submitting data to trakt.tv: %s' % result.text)
        else:
            self.log.info('Data successfully sent to trakt.tv: ' + result.text)
    
    @plugin.priority(-255)
    def on_task_output(self, task, config):
        """Finds accepted movies and submits them to the user trakt watchlist."""
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
        # Sort out the data
        found = {'shows': {}, 'movies': {}}
        for entry in task.accepted:
            serie = None
            if entry.get('tvdb_id'):
                serie = found['shows'].setdefault(entry['tvdb_id'], 
                                                  {'tvdb_id': entry['tvdb_id']})
            elif entry.get('series_name'):
                serie = found['shows'].setdefault(entry['series_name'].lower(), 
                                                  {'title': entry['series_name'].lower()})
            elif entry.get('imdb_id'):
                found['movies'].setdefault(entry['imdb_id'], 
                                           {'imdb_id': entry['imdb_id']})
            elif entry.get('tmdb_id'):
                found['movies'].setdefault(entry['tmdb_id'], 
                                           {'tmdb_id': entry['tmdb_id']})
            elif entry.get('movie_name') and entry.get('movie_year'):
                found['movies'].setdefault(entry['movie_name'].lower(), 
                                           {'title': entry['movie_name'], 
                                            'year': entry['movie_year']})
            if serie:
                if entry.get('series_season') and entry.get('series_episode'):
                    serie.setdefault('episodes', []).append({'season': entry['series_season'], 
                                                             'episode': entry['series_episode']})
                else:
                    serie['whole'] = True
        if not (found['shows'] or found['movies']):
            self.log.debug('Nothing to submit to trakt.')
            return
        # Make the calls
        if not list_name in ['watchlist', 'seen', 'library']:
            post_params = {'username': config['username'], 
                           'password': config['password'], 
                           'slug': list_name, 'items': []}
            for item in found['movies'].itervalues():    
                data = {'type': 'movie'}
                data.update(item)
                post_params['items'].append(data)
            for item in found['shows'].itervalues():
                if 'whole' in item:
                    data = {'type': 'show'}
                    data.update(item)
                    del data['whole']
                    if 'episodes' in data:
                        del data['episodes']
                    post_params['items'].append(data)
                else:
                    for epi in item['episodes']:
                        data = {'type': 'episode'}
                        data.update(item)
                        data.update(epi)
                        del data['episodes']
                        post_params['items'].append(data)
            post_url = 'http://api.trakt.tv/lists/items/%s/%s' % \
                ('delete' if self.remove else 'add', config['api_key'])
            self.submit_data(task, post_url, post_params)
        else:
            base_params = {'username': config['username'], 'password': config['password']}
            if self.remove:
                list_name = 'un' + list_name
            post_params = {'movies': []}
            post_params.update(base_params)
            for item in found['movies'].itervalues():
                post_params['movies'].append(item)
            if post_params['movies']:
                post_url = 'http://api.trakt.tv/movie/%s/%s' % (list_name, config['api_key'])
                self.submit_data(task, post_url, post_params)
            for item in found['shows'].itervalues():
                if item.get('whole'):
                    post_params = item.copy()
                    post_params.update(base_params)
                    del post_params['whole']
                    if 'episodes' in post_params:
                        del post_params['episodes']
                    post_url = 'http://api.trakt.tv/show/%s/%s' % (list_name, config['api_key'])
                    self.submit_data(task, post_url, post_params)
                else:
                    post_params = {'episodes': item['episodes']}
                    post_params.update(base_params)
                    post_params.update(item)
                    post_url = 'http://api.trakt.tv/show/episode/%s/%s' % (list_name, config['api_key'])
                    self.submit_data(task, post_url, post_params)


class TraktAdd(TraktSubmit):
    """Add all accepted elements in your trakt.tv watchlist/library/seen or custom list."""
    remove = False
    log = logging.getLogger('trakt_add')


class TraktRemove(TraktSubmit):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    remove = True
    log = logging.getLogger('trakt_remove')


@event('plugin.register')
def register_plugin():
    plugin.register(TraktAdd, 'trakt_add', api_ver=2)
    plugin.register(TraktRemove, 'trakt_remove', api_ver=2)
