from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging
from urlparse import urljoin

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json
from flexget.utils.trakt import API_URL, get_session, make_list_slug

log = logging.getLogger('trakt_emit')


class TraktEmit(object):
    """
    Creates an entry for the latest or the next item in your watched or collected
    episodes in your trakt account.

    Syntax:

    trakt_emit:
      username: <value>
      position: <last|next>
      context: <collect|collected|watch|watched>
      list: <value>

    Options username, password and api_key are required.

    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'position': {'type': 'string', 'enum': ['last', 'next'], 'default': 'next'},
            'context': {'type': 'string', 'enum': ['watched', 'collected'], 'default': 'watched'},
            'list': {'type': 'string'}
        },
        'required': ['username'],
        'additionalProperties': False
    }

    def get_trakt_data(self, task, config, url, null_data=None):
        log.debug('Opening %s' % url)
        auth = {'username': config['username'],
                'password': hashlib.sha1(config['password']).hexdigest()}
        try:
            data = task.requests.get(url, data=json.dumps(auth)).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)

        def check_auth():
            auth_url = 'http://api.trakt.tv/account/test/' + config['api_key']
            if task.requests.post(auth_url, data=json.dumps(auth), raise_status=False).status_code != 200:
                raise plugin.PluginError('Authentication to trakt failed.')

        if not data:
            check_auth()
            log.warning('No data returned from trakt.')
            return null_data
        if 'error' in data:
            check_auth()
            raise plugin.PluginError('Error getting trakt list: %s' % data['error'])
        return data

    def on_task_input(self, task, config):
        session = get_session(config['username'], config.get('password'))
        listed_series = {}
        if config.get('list'):
            url = urljoin(API_URL, 'users/%s/' % config['username'])
            if config['list'] in ['collection', 'watchlist', 'watched']:
                url = urljoin(url, '%s/shows' % config['list'])
            else:
                url = urljoin(url, 'lists/%s/items' % make_list_slug(config['list']))
            try:
                data = session.get(url).json()
            except RequestException as e:
                raise plugin.PluginError('Unable to get trakt list `%s`: %s' % (config['list'], e))
            if not data:
                log.warning('The list "%s" is empty.' % config['list'])
                return
            for item in data:
                if item['type'] == 'show':
                    trakt_id = item['show']['ids']['trakt']
                    listed_series[trakt_id] = item['show']['title']
        context = config['context']
        if context == 'collected':
            context = 'collection'
        entries = []
        for trakt_id, show in listed_series.iteritems():
            url = urljoin(API_URL, 'shows/%s/progress/%s' % (trakt_id, context))
            try:
                data = session.get(url).json()
            except RequestException as e:
                raise plugin.PluginError('TODO: error message')
            if config['position'] == 'next' and item.get('next_episode'):
                # If the next episode is already in the trakt database, we'll get it here
                eps = data['next_episode']['season']
                epn = data['next_episode']['number']
            else:
                # If we need last ep, or next_episode was not provided, search for last ep
                for seas in reversed(item['seasons']):
                    # Find the first season with collected/watched episodes
                    if seas['completed'] > 0:
                        eps = seas['season']
                        # Pick the highest collected/watched episode
                        epn = max(int(num) for (num, seen) in seas['episodes'].iteritems() if seen)
                        # If we are in next episode mode, we have to increment this number
                        if config['position'] == 'next':
                            if seas['percentage'] >= 100:
                                # If there are more episodes to air this season, next_episode handled it above
                                eps += 1
                                epn = 1
                            else:
                                epn += 1
                        break
            if eps and epn:
                entry = self.make_entry(item['show']['tvdb_id'], item['show']['title'], eps, epn,
                                        item['show']['imdb_id'])
                entries.append(entry)


            # If we were given an explicit list in next mode, fill in any missing series with S01E01 entries
            if config['position'] == 'next':
                for tvdb_id in listed_series:
                    entries.append(self.make_entry(tvdb_id, listed_series[tvdb_id], 1, 1))
        return entries

    def make_entry(self, tvdb_id, name, season, episode, imdb_id=None):
        entry = Entry()
        entry['tvdb_id'] = int(tvdb_id)
        entry['series_name'] = name
        entry['series_season'] = season
        entry['series_episode'] = episode
        entry['series_id_type'] = 'ep'
        entry['series_id'] = 'S%02dE%02d' % (season, episode)
        entry['title'] = entry['series_name'] + ' ' + entry['series_id']
        entry['url'] = 'http://thetvdb.com/?tab=series&id=%s' % tvdb_id
        if imdb_id:
            entry['imdb_id'] = imdb_id
        return entry


@event('plugin.register')
def register_plugin():
    plugin.register(TraktEmit, 'trakt_emit', api_ver=2)
