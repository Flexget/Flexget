from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json

log = logging.getLogger('trakt_watched')


class TraktWatched(object):
    """
    Query trakt.tv for watched episodes to set the trakt_watched flag on entries.
    Uses tvdb_id or imdb_id or series_name, plus series_season and series_episode 
    fields (metainfo_series and thetvdb_lookup or trakt_lookup plugins will do).
    
    Example task:
    
      Purge watched episodes:
        find:
          path:
            - D:\Media\Incoming\series
          regexp: '.*\.(avi|mkv|mp4)$'
          recursive: yes
        metainfo_series: yes
        thetvdb_lookup: yes
        trakt_watched_lookup:
          username: xxx
          password: xxx
          api_key: xxx
        if:
          - trakt_watched: accept
        move:
          to: "D:\\Media\\Purge\\{{ tvdb_series_name|default(series_name) }}"
          clean_source: 10
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'}
        },
        'required': ['username', 'api_key'],
        'additionalProperties': False
    }
    
    # Run after metainfo_series and thetvdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        if not task.entries:
            return
        url = 'http://api.trakt.tv/user/library/shows/watched.json/%s/%s' % \
            (config['api_key'], config['username'])
        auth = None
        if 'password' in config:
            auth = {'username': config['username'],
                    'password': hashlib.sha1(config['password']).hexdigest()}
        try:
            log.debug('Opening %s' % url)
            data = task.requests.get(url, data=json.dumps(auth)).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)

        def check_auth():
            if task.requests.post('http://api.trakt.tv/account/test/' + config['api_key'],
                                  data=json.dumps(auth), raise_status=False).status_code != 200:
                raise plugin.PluginError('Authentication to trakt failed.')

        if not data:
            check_auth()
            self.log.warning('No data returned from trakt.')
            return
        if 'error' in data:
            check_auth()
            raise plugin.PluginError('Error getting trakt list: %s' % data['error'])
        log.verbose('Received %d series records from trakt.tv' % len(data))
        # the index will speed the work if we have a lot of entries to check
        index = {}
        for idx, val in enumerate(data):
            index[val['title']] = index[int(val['tvdb_id'])] = index[val['imdb_id']] = idx
        for entry in task.entries:
            if not (entry.get('series_name') and entry.get('series_season') and entry.get('series_episode')):
                continue
            entry['trakt_watched'] = False
            if 'tvdb_id' in entry and entry['tvdb_id'] in index:
                series = data[index[entry['tvdb_id']]]
            elif 'imdb_id' in entry and entry['imdb_id'] in index:
                series = data[index[entry['imdb_id']]]
            elif 'series_name' in entry and entry['series_name'] in index:
                series = data[index[entry['series_name']]]
            else:
                continue
            for s in series['seasons']:
                if s['season'] == entry['series_season']:
                    entry['trakt_watched'] = entry['series_episode'] in s['episodes']
                    break
            log.debug('The result for entry "%s" is: %s' % (entry['title'], 
                'Watched' if entry['trakt_watched'] else 'Unwatched'))


@event('plugin.register')
def register_plugin():
    plugin.register(TraktWatched, 'trakt_watched_lookup', api_ver=2)
