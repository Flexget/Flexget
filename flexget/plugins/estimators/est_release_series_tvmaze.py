from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime
import re
from flexget import plugin
from flexget.event import event

try:
    # TODO implement TVMaze API internally
    from pytvmaze import get_show, lookup_tvrage, lookup_tvdb
except ImportError as e:
    raise plugin.PluginError('Could not import from pytvmaze')

log = logging.getLogger('est_series_tvmaze')


class EstimatesSeriesTVMaze(object):
    @plugin.priority(2)
    def estimate(self, entry):
        if not all(field in entry for field in ['series_name', 'series_season', 'series_episode']):
            return
        series_name = re.sub('[()]', '', entry['series_name'])  # Remove parenthesis from year if present
        season = entry['series_season']
        episode_number = entry['series_episode']
        log.verbose('Search TVMaze for airdate of %s season %s episode %s' % (series_name, season, episode_number))
        if entry.get('tvmaze_id'):
            log.debug('Searching via TVMaze ID')
            tvmaze_show = get_show(int(entry.get('tvmaze_id')))
        elif entry.get('tvdb_id'):
            log.debug('Searching via TVDB ID')
            tvmaze_show = get_show(int(lookup_tvdb(entry.get('tvdb_id'))['id']))
        elif entry.get('tvrage_id'):
            log.debug('Searching via TVRage ID')
            tvmaze_show = get_show(int(lookup_tvdb(entry.get('tvrage_id'))['id']))
        else:
            log.debug('Searching via show name')
            tvmaze_show = get_show(series_name)
        if not tvmaze_show:
            log.debug('TVMaze did not find match for %s' % series_name)
            return
        episode = tvmaze_show[season][episode_number]
        if episode:
            return datetime.strptime(episode.airdate, '%Y-%m-%d')
        else:
            log.debug('No episode info obtained from TVMaze for %s season %s episode %s' % (
                entry['series_name'], entry['series_season'], entry['series_episode']))
        return


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesSeriesTVMaze, 'est_series_tvmaze', groups=['estimate_release'], api_ver=2)
