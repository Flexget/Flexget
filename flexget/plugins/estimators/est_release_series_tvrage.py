from __future__ import unicode_literals, division, absolute_import
from datetime import timedelta, datetime
import logging

from flexget import plugin
from flexget.event import event
from flexget.manager import Session

try:
    from flexget.plugins.api_tvrage import lookup_series
    api_tvrage = True
except ImportError as e:
    api_tvrage = False

log = logging.getLogger('est_series_tvrage')


class EstimatesSeriesTVRage(object):
    @plugin.priority(1)
    def estimate(self, entry):
        if not all(field in entry for field in ['series_name', 'series_season', 'series_episode']):
            return
        season = entry['series_season']
        if entry.get('series_id_type') == 'sequence':
            # Tvrage has absolute numbered shows under season 1
            season = 1
        log.debug("Querying release estimation for %s S%02dE%02d ..." %
                  (entry['series_name'], season, entry['series_episode']))
        with Session(expire_on_commit=False) as session:
            try:
                series_info = lookup_series(name=entry['series_name'], session=session)
            except LookupError as e:
                log.debug('tvrage lookup error: %s' % e)
            except OverflowError:
                # There is a bug in tvrage library on certain platforms if an episode is marked as airing
                # before 1970. We can safely assume the episode has been released. See #2739
                log.debug('tvrage library crash due to date before 1970, assuming released')
                return datetime(1970, 1, 1)
            else:
                if series_info:
                    try:
                        episode_info = series_info.find_episode(season, entry['series_episode'])
                        if episode_info:
                            return episode_info.airdate
                        else:
                            # If episode does not exist in tvrage database, we always return a future date
                            log.verbose('%s S%02dE%02d does not exist in tvrage database, assuming unreleased',
                                        series_info.name, season, entry['series_episode'])
                            return datetime.now() + timedelta(weeks=4)
                    except Exception as e:
                        log.exception(e)
                else:
                    log.debug('No series info obtained from TVRage to %s' % entry['series_name'])

        log.debug('No episode info obtained from TVRage for %s season %s episode %s' %
                  (entry['series_name'], entry['series_season'], entry['series_episode']))


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesSeriesTVRage, 'est_series_tvrage', groups=['estimate_release'], api_ver=2)
