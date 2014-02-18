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
    Uses tvdb_id, series_season and series_episode fields (metainfo_series plus 
    thetvdb_lookup or trakt_lookup plugins can provide them).
    
    Example task:
    
      Purge watched episodes:
        find:
          path:
            - D:\Media\Incoming\series
          regexp: '.*\.(avi|mkv|mp4)$'
          recursive: yes
        metainfo_series: yes
        thetvdb_lookup: yes
        trakt_watched:
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
        series = {}
        for item in data:
            series[item['tvdb_id']] = item
        for entry in task.entries:
            if entry.get('tvdb_id') and entry.get('series_season') and entry.get('series_episode'):
                entry['trakt_watched'] = False
                if series.get(entry['tvdb_id']):
                    for s in series[entry['tvdb_id']]['seasons']:
                        if s['season'] == entry['series_season']:
                            entry['trakt_watched'] = entry['series_episode'] in s['episodes']


@event('plugin.register')
def register_plugin():
    plugin.register(TraktWatched, 'trakt_watched', api_ver=2)
