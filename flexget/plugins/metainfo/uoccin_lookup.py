from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import os

from flexget import plugin
from flexget.event import event
from flexget.utils import json


def load_uoccin_data(path):
    udata = {}
    ufile = os.path.join(path, 'uoccin.json')
    if os.path.exists(ufile):
        try:
            with open(ufile, 'r') as f:
                udata = json.load(f)
        except Exception as err:
            raise plugin.PluginError('error reading %s: %s' % (ufile, err))
    udata.setdefault('movies', {})
    udata.setdefault('series', {})
    return udata


class UoccinLookup(object):

    schema = { 'type': 'string', 'format': 'path' }
    
    # Run after metainfo_series / thetvdb_lookup / imdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        """Retrieves all the information found in the uoccin.json file for the entries.
        
        Example::
            
            uoccin_lookup: /path/to/gdrive/uoccin
        
        Resulting fields on entries:
        
        on series (requires tvdb_id):
        - uoccin_watchlist (true|false)
        - uoccin_rating (integer)
        - uoccin_tags (list)
        
        on episodes (requires tvdb_id, series_season and series_episode):
        - uoccin_collected (true|false)
        - uoccin_watched (true|false)
        - uoccin_subtitles (list of language codes)
        (plus the 3 series specific fields)
        
        on movies (requires imdb_id):
        - uoccin_watchlist (true|false)
        - uoccin_collected (true|false)
        - uoccin_watched (true|false)
        - uoccin_rating (integer)
        - uoccin_tags (list)
        - uoccin_subtitles (list of language codes)
        
        """
        if not task.entries:
            return
        udata = load_uoccin_data(config)
        movies = udata['movies']
        series = udata['series']
        for entry in task.entries:
            entry['uoccin_watchlist'] = False
            entry['uoccin_collected'] = False
            entry['uoccin_watched'] = False
            entry['uoccin_rating'] = None
            entry['uoccin_tags'] = []
            entry['uoccin_subtitles'] = []
            if 'tvdb_id' in entry:
                ser = series.get(str(entry['tvdb_id']))
                if ser is None:
                    continue
                entry['uoccin_watchlist'] = ser.get('watchlist', False)
                entry['uoccin_rating'] = ser.get('rating')
                entry['uoccin_tags'] = ser.get('tags', [])
                if all(field in entry for field in ['series_season', 'series_episode']):
                    season = str(entry['series_season'])
                    episode = entry['series_episode']
                    edata = ser.get('collected', {}).get(season, {}).get(str(episode))
                    entry['uoccin_collected'] = isinstance(edata, list)
                    entry['uoccin_subtitles'] = edata if entry['uoccin_collected'] else []
                    entry['uoccin_watched'] = episode in ser.get('watched', {}).get(season, [])
            elif 'imdb_id' in entry:
                try:
                    mov = movies.get(entry['imdb_id'])
                except plugin.PluginError as e:
                    self.log.trace('entry %s imdb failed (%s)' % (entry['imdb_id'], e.value))
                    continue
                if mov is None:
                    continue
                entry['uoccin_watchlist'] = mov.get('watchlist', False)
                entry['uoccin_collected'] = mov.get('collected', False)
                entry['uoccin_watched'] = mov.get('watched', False)
                entry['uoccin_rating'] = mov.get('rating')
                entry['uoccin_tags'] = mov.get('tags', [])
                entry['uoccin_subtitles'] = mov.get('subtitles', [])


@event('plugin.register')
def register_plugin():
    plugin.register(UoccinLookup, 'uoccin_lookup', api_ver=2)
