from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from datetime import datetime
from requests import RequestException
from sqlalchemy import Column, Integer, DateTime

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils import json

Base = db_schema.versioned_base('trakt_watched', 0)


class TraktWatched(Base):
    __tablename__ = 'trakt_watched'

    tvdb_id = Column(Integer, primary_key=True, autoincrement=False)
    season = Column(Integer)
    episode = Column(Integer)
    last_update = Column(DateTime)


class TraktSeenLookup(object):
    """
    Evaluate data collected by trakt_seen_update to set a trakt.tv watched flag 
    (tsl_ep_watched) for episodes found in entries. Uses tvdb_id, series_season 
    and series_episode.
    
    Example:
    
      trakt_seen_lookup: yes
    
    
    Set the following fields in entries having a tvdb_id:
    
    - tsl_last_season:   last watched episode season number (int).
    - tsl_last_episode:  last watched episode episode number (int).
    - tsl_last_ep_id:    last watched episode id (string, S00E00 format).
    - tsl_last_update:   last update time (datetime).
    
    Set this field too in entries having series_season and series_episode:
    
    - tsl_ep_watched:    watched status (boolean).
    
    
    Note: entries about series not found in trakt_seen_update plugin collected 
    data will not have any of the above fields set.
    
    """

    schema = {'type': 'boolean'}
    
    log = logging.getLogger('trakt_seen_lookup')
    
    # Run after thetvdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        # check if explicitly disabled (value set to false)
        if config is False:
            return
        for entry in task.entries:
            if entry.get('tvdb_id'):
                series = task.session.query(TraktWatched).filter(TraktWatched.tvdb_id == entry['tvdb_id']).first()
                if series:
                    entry['tsl_last_season'] = series.season
                    entry['tsl_last_episode'] = series.episode
                    entry['tsl_last_ep_id'] = 'S%02dE%02d' % (series.season, series.episode)
                    entry['tsl_last_update'] = series.last_update
                    if entry.get('series_season') and entry.get('series_episode'):
                        entry['tsl_ep_watched'] = entry['series_season'] < series.season or \
                            (entry['series_season'] == series.season and entry['series_episode'] <= series.episode)


class TraktSeenUpdate(object):
    """
    Collect trakt.tv last watched episodes for series found in entries (needs a 
    valid tvdb_id per series).
    
    Example task::
    
      my_watched_stuff:
        disable_builtins:
          - seen
          - backlog
          - retry_failed
        trakt_list:
          username: myusername
          password: mypassword
          api_key: myapikey
          strip_dates: yes
          series: watchlist
        accept_all: yes
        trakt_seen_update:
          username: myusername
          password: mypassword
          api_key: myapikey
    
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
    
    log = logging.getLogger('trakt_seen_update')
    
    def on_task_output(self, task, config):
        """
        Configuration::
            trakt_seen_update:
                username: Your trakt.tv username.
                api_key: Your trakt.tv API key.
        """
        if not config or not task.accepted:
            return
        shows = []
        for entry in task.accepted:
            if not 'tvdb_id' in entry:
                self.log.debug('"%s" has no tvdb_id, ignored' % entry['title'])
                continue
            if not entry['tvdb_id'] in shows:
                shows.append(str(entry['tvdb_id']))
        if not shows:
            self.log.verbose("No series info found in entries, we're done.")
            return
        auth = None
        if 'password' in config:
            auth = {'username': config['username'],
                    'password': hashlib.sha1(config['password']).hexdigest()}
        url = 'http://api.trakt.tv/user/progress/watched.json/%s/%s/%s' % \
            (config['api_key'], config['username'], ','.join(shows))
        self.log.debug('Opening url %s ...' % url)
        try:
            data = task.requests.get(url, data=json.dumps(auth)).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)
        if not data:
            self.log.info('No data returned: the user does not have seen records on trakt.tv for these shows.')
            return
        if not isinstance(data, list):
            self.log.error('Unexpected response from trakt.tv, perhaps API is changed?')
            return
        def check_auth():
            if task.requests.post('http://api.trakt.tv/account/test/' + config['api_key'],
                data=json.dumps(auth), raise_status=False).status_code != 200:
                raise plugin.PluginError('Authentication to trakt failed.')
        if 'error' in data:
            check_auth()
            raise plugin.PluginError('Error getting trakt list: %s' % data['error'])
        if not data:
            check_auth()
            self.log.warning('No data returned from trakt.')
            return
        # response is a list with series info as elements
        for show in data:
            title = show['show']['title']
            tvdb_id = show['show']['tvdb_id']
            self.log.debug('Checking watched status for "%s" (TVDB: %s)...' % (title, tvdb_id))
            try:
                lseas = show['seasons'][-1]['season']
                lepis = show['seasons'][-1]['aired']
                if show['progress']['percentage'] < 100:
                    for seas in reversed(show['seasons']):
                        lepis = seas['aired']
                        for epis in reversed(range(seas['aired'])):
                            if seas['episodes'][str(epis+1)]:
                                break
                            lepis -= 1
                        else:
                            lseas -= 1
                            continue
                        break
            except Exception as e:
                self.log.error('Unexpected item structure, perhaps API is changed?')
                return
            series = task.session.query(TraktWatched).filter(TraktWatched.tvdb_id == tvdb_id).first()
            if not series:
                self.log.debug('No data stored for "%s", creating record...' % title)
                series = TraktWatched()
                series.tvdb_id = tvdb_id
                task.session.add(series)
            elif (series.season == lseas and series.episode == lepis):
                self.log.verbose('Last watched episode for "%s" has not changed.' % title)
                continue
            series.season = lseas
            series.episode = lepis
            series.last_update = datetime.now()
            self.log.info('Last watched episode set to S%02dE%02d for "%s"' % (lseas, lepis, title))


@event('plugin.register')
def register_plugin():
    plugin.register(TraktSeenLookup, 'trakt_seen_lookup', api_ver=2)
    plugin.register(TraktSeenUpdate, 'trakt_seen_update', api_ver=2)
