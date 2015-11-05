from __future__ import unicode_literals, division, absolute_import
import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugins.api_trakt import get_api_url, get_session

log = logging.getLogger('trakt_collected')

MOVIE_IDS = [
    'tmdb_id',
    'imdb_id',
    'movie_name'
]

SHOW_IDS = [
    'tvdb_id',
    'tmdb_id',
    'imdb_id',
    'series_name'
]


class TraktCollected(object):
    """
    Query trakt.tv for episodes or movies in the user collection to set the trakt_in_collection flag on entries.
    Uses tmdb_id, tvdb_id or imdb_id or series_name or movie_name, plus series_season and series_episode fields
    (metainfo_series and thetvdb_lookup or trakt_lookup or imdb_lookup or tmdb_lookup plugins will do).
    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'account': {'type': 'string'},
            'type': {'type': 'string', 'enum': ['movies', 'shows'], 'default': 'shows'}
        },
        'required': ['username'],
        'additionalProperties': False
    }
    
    # Run after metainfo_series and thetvdb_lookup
    @plugin.priority(100)
    def on_task_metainfo(self, task, config):
        if not task.entries:
            return
        url = get_api_url('users', config['username'], 'collection', config['type'])
        session = get_session(config['username'], account=config.get('account'))
        try:
            log.debug('Opening %s' % url)
            data = session.get(url).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)

        if not data:
            log.warning('No data returned from trakt.')
            return
        log.verbose('Received %d series records from trakt.tv' % len(data))
        # the index will speed the work if we have a lot of entries to check
        index = {}
        if config['type'] == 'shows':
            for idx, val in enumerate(data):
                v = val.get('show')
                index[v['title']] = index[int(v['ids']['tvdb'])] = \
                    index[v['ids']['imdb']] = index[v['ids']['tmdb']] = idx
            for entry in task.entries:
                if not (entry.get('series_name') and entry.get('series_season') and entry.get('series_episode')):
                    continue
                entry['trakt_in_collection'] = False
                series = None
                for id in SHOW_IDS:
                    if id in entry and entry[id] in index:
                        series = data[index[entry[id]]]
                if not series:
                    continue
                for s in series['seasons']:
                    if s['number'] == entry['series_season']:
                        # extract all episode numbers currently in collection for the season number
                        episodes = [ep['number'] for ep in s['episodes']]
                        entry['trakt_in_collection'] = entry['series_episode'] in episodes
                        break
                log.debug('The result for entry "%s" is: %s' % (entry['title'],
                          'Owned' if entry['trakt_in_collection'] else 'Not owned'))
        else:
            for idx, val in enumerate(data):
                v = val.get('movie')
                index[v['title']] = index[int(v['ids']['tmdb'])] = index[v['ids']['imdb']] = idx
            for entry in task.entries:
                if not (entry.get('movie_name') or entry.get('imdb_id') or entry.get('tmdb_id')):
                    continue
                movie = None
                for id in MOVIE_IDS:
                    if id in entry and entry[id] in index:
                        movie = data[index[entry[id]]]
                entry['trakt_in_collection'] = True if movie else False
                log.debug('The result for entry "%s" is: %s' % (entry['title'],
                          'Owned' if entry['trakt_in_collection'] else 'Not owned'))


@event('plugin.register')
def register_plugin():
    plugin.register(TraktCollected, 'trakt_collected_lookup', api_ver=2)
