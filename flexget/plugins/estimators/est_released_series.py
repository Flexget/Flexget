from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('est_released_series')


class EstimatesReleasedSeries(object):
    """
    Front-end for series estimator plugins that estimate release times
    for series)
    """

    def estimate(self, entry):
        """
        Estimate release schedule for Entry

        :param entry:
        :return: estimated date of released for the entry, None if it can't figure it out
        """
        log.debug(entry['title'])
        estimators = [e.instance.estimate for e in plugin.get_plugins(group='estimate_release_series')]
        for estimator in sorted(estimators, key=lambda e: getattr(e, 'priority', plugin.DEFAULT_PRIORITY),
                                reverse=True):
            estimate = estimator(entry)  # return first successful estimation
            if estimate is not None:
                return estimate


@event('plugin.register')
def register_plugin():
    plugin.register(EstimatesReleasedSeries, 'est_released_series', groups=['estimate_release'], api_ver=2)
