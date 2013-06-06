from __future__ import unicode_literals, division, absolute_import
from datetime import timedelta
import logging

from sqlalchemy import desc, func

from flexget.manager import Session
from flexget.plugin import register_plugin, priority, DependencyError
from flexget.utils.tools import multiply_timedelta
try:
    from flexget.plugins.filter.series import Series, Episode
except ImportError:
    raise DependencyError(issued_by='est_released_series', missing='series plugin', silent=True)

log = logging.getLogger('est_series')


class EstimatesReleasedSeries(object):

    @priority(0)  # Run only if better online lookups fail
    def estimate(self, entry):
        if all(field in entry for field in ['series_name', 'series_season', 'series_episode']):
            session = Session()
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


register_plugin(EstimatesReleasedSeries, 'est_released_series', groups=['estimate_release'], api_ver=2)
