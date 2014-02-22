from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('trakt_emit')


class TraktEmit(object):
    """
    Creates an entry for the latest or the next item in your watched or collected 
    episodes in your trakt account.

    Syntax:

    trakt_emit:
      username: <value>
      api_key: <value>
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
            'api_key': {'type': 'string'},
            'position': {'enum': ['last', 'next'], 'default': ['next']},
            'context': {'enum': ['watched', 'collected'], 'default': ['watched']},
            'list': {'type': 'string'}
        },
        'required': ['username', 'password', 'api_key'],
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
            if task.requests.post('http://api.trakt.tv/account/test/' + config['api_key'],
                data=json.dumps(auth), raise_status=False).status_code != 200:
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
        series = {}
        if config.get('list'):
            url = 'http://api.trakt.tv/user/list.json/%s/%s/%s' % \
                (config['api_key'], config['username'], config['list'])
            data = self.get_trakt_data(task, config, url, null_data={})
            if not data.get('items') or len(data['items']) <= 0:
                log.warning('The list "%s" is empty.' % config['list'])
                return
            for item in data['items']:
                if item['type'] in ['show', 'season', 'episode'] and \
                    not item['show']['tvdb_id'] in series:
                    series[item['show']['tvdb_id']] = item['show']['title']
        url = 'http://api.trakt.tv/user/progress/%s.json/%s/%s' % \
            (config['context'], config['api_key'], config['username'])
        if series:
            url += '/' + ','.join(series.keys())
        data = self.get_trakt_data(task, config, url, null_data=[])
        entries = []
        def add_entry(tvdb_id, name, season, episode, imdb_id=None):
            tvdb_id = str(tvdb_id) # sometimes it's a number
            entry = Entry()
            entry['tvdb_id'] = tvdb_id
            entry['series_name'] = name
            entry['series_season'] = season
            entry['series_episode'] = episode
            entry['series_id_type'] = 'ep'
            entry['series_id'] = 'S%02dE%02d' % (season, episode)
            entry['title'] = entry['series_name'] + ' ' + entry['series_id']
            entry['url'] = 'http://thetvdb.com/?tab=series&id=' + tvdb_id
            if imdb_id:
                entry['imdb_id'] = imdb_id
            entries.append(entry)
            log.verbose('Entry added: "%s", %s' % (entry['title'], entry['url']))
            return entry
        for item in data:
            if item['show']['tvdb_id'] == 0: # (sh)it happens with filtered queries
                continue
            eps = epn = 0
            if config['position'] == 'last':
                for seas in reversed(item['seasons']):
                    eps = seas['season']
                    epn = seas['aired']
                    if seas['percentage'] >= 100:
                        break
                    elif seas['percentage'] > 0:
                        for i in reversed(range(seas['aired'])):
                            if seas['episodes'][str(epn)]:
                                break
                            epn -= 1
                        else:
                            continue
                        break
            elif item.get('next_episode'):
                eps = item['next_episode']['season']
                epn = item['next_episode']['number']
            if eps and epn:
                entry = add_entry(item['show']['tvdb_id'], item['show']['title'], 
                                  eps, epn, item['show']['imdb_id'])
                if entry['tvdb_id'] in series:
                    del series[entry['tvdb_id']]
        if config['position'] == 'next':
            for tvdb_id in series.keys():
                add_entry(tvdb_id, series[tvdb_id], 1, 1)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TraktEmit, 'trakt_emit', api_ver=2)
