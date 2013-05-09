from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin
from flexget.plugins.api_tvrage import lookup_series

log = logging.getLogger('est_series')


class EstimatesRelasedSeries(object):

    def get_serie_info(self, serie_name):
        return lookup_series(name=serie_name)

    def is_released(self, task, entry):
        if ('serie_name' in entry and 'serie_episode' in entry and 'serie_season' in entry):
            log.info("Checking %s (%s/%s/%s)" % (entry['title'], entry['serie_name'], entry['serie_season'], entry['serie_episode']))
            serie_info = self.get_serie_info(entry['serie_name'])
            if serie_info is None:
                log.debug("No serie info obtained from TVRage -> res='none'")
                return None
            try:
                wanted_episode_info = serie_info.season(entry['serie_season']).episode(entry['serie_episode'])
            except:
                wanted_episode_info = None

            if wanted_episode_info is None:
                log.debug("No wanted episode info obtained from TVRage -> res='none'")
                return None
            return wanted_episode_info.airdate
        return None

register_plugin(EstimatesRelasedSeries, 'est_relased_series', groups=['estimate_released'])
