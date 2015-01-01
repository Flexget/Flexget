from __future__ import unicode_literals, division, absolute_import
from datetime import timedelta, datetime
import logging

from sqlalchemy import desc, func

from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import multiply_timedelta
try:
    from flexget.plugins.api_tvrage import lookup_series
    api_tvrage = True
except ImportError as e:
    api_tvrage = False
try:
    from flexget.plugins.filter.series import Series, Episode
except ImportError:
    raise plugin.DependencyError(issued_by='est_released_series', missing='series plugin', silent=True)

log = logging.getLogger('est_series')


class EstimatesReleasedSeries(object):

    @plugin.priority(0)  # Run only if better online lookups fail
    def estimate(self, entry):
        if all(field in entry for field in ['series_name', 'series_season', 'series_episode']):
            # Try to get airdate from tvrage first
            if api_tvrage:
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

            # If no results from tvrage, estimate a date based on series history
            with Session() as session:
                series = session.query(Series).filter(Series.name == entry['series_name']).first()
                if not series:
                    return
                episodes = (session.query(Episode).join(Episode.series).
                            filter(Episode.season != None).
                            filter(Series.id == series.id).
                            filter(Episode.season == func.max(Episode.season).select()).
                            order_by(desc(Episode.number)).limit(2).all())

                if len(episodes) < 2:
                    return
                # If last two eps were not contiguous, don't guess
                if episodes[0].number != episodes[1].number + 1:
                    return
                last_diff = episodes[0].first_seen - episodes[1].first_seen
                # If last eps were grabbed close together, we might be catching up, don't guess
                # Or, if last eps were too far apart, don't guess
                # TODO: What range?
                if last_diff < timedelta(days=2) or last_diff > timedelta(days=10):
                    return
                # Estimate next season somewhat more than a normal episode break
                if entry['series_season'] > episodes[0].season:
                    # TODO: How big should this be?
                    return episodes[0].first_seen + multiply_timedelta(last_diff, 2)
                # Estimate next episode comes out about same length as last ep span, with a little leeway
                return episodes[0].first_seen + multiply_timedelta(last_diff, 0.9)


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesReleasedSeries, 'est_released_series', groups=['estimate_release'], api_ver=2)
