from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin
from flexget.plugins.api_tvrage import lookup_series

log = logging.getLogger('est_series')


class EstimatesRelasedSeries(object):

    def get_series_info(self, series_name):
        return lookup_series(name=series_name)

    def estimate(self, entry):
        if 'series_name' in entry and 'series_episode' in entry and 'series_season' in entry:
            log.verbose("Querying release estimation for %s S%02dE%02d ..." %
                        (entry['series_name'], entry['series_season'], entry['series_episode']))
            series_info = self.get_series_info(entry['series_name'])
            if series_info is None:
                log.debug('No series info obtained from TVRage to %s' % entry['series_name'])
                return None
            try:
                season_info = series_info.season(entry['series_season'])
                if season_info:
                    episode_info = season_info.episode(entry['series_episode'])
                    if episode_info:
                        return episode_info.airdate
            # this may occur if we ask for a season or an episode that doesn't exists and we don't want a messy log
            # with "normal" exception
            except KeyError as e:
                return None
            except Exception as e:
                log.exception(e)

            log.debug('No episode info obtained from TVRage for %s season %s episode %s' %
                      (entry['series_name'], entry['series_season'], entry['series_episode']))


register_plugin(EstimatesRelasedSeries, 'est_relased_series', groups=['estimate_release'])
