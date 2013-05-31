from __future__ import unicode_literals, division, absolute_import
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
            episodes = (session.query(Episode).join(Series).
                filter(Episode.season != None).
                filter(Series.id == series.id).
                filter(Episode.season == func.max(Episode.season).select()).
                order_by(desc(Episode.number)).limit(2).all())
            if len(episodes) < 2:
                return
            if episodes[0].number != episodes[0].number + 1:
                return
            last_diff = episodes[0].first_seen - episodes[1].first_seen
            return episodes[0].first_seen + multiply_timedelta(last_diff, 0.9)
            # TODO: Some fancier logic? Season break estimates?


register_plugin(EstimatesReleasedSeries, 'est_released_series', groups=['estimate_release'], api_ver=2)
