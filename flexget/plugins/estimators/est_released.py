import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('est_released')


class EstimateRelease(object):
    """
    Front-end for estimator plugins that estimate release times
    for various things (series, movies).
    """

    def estimate(self, entry, preferred_estimator=None):
        """
        Estimate release schedule for Entry

        :param entry:
        :return: estimated date of released for the entry, None if it can't figure it out
        """

        log.debug(entry['title'])
        estimators = [e.instance for e in plugin.get_plugins(group='estimate_release')]
        estimators.sort(key=lambda e: getattr(e, 'priority', plugin.DEFAULT_PRIORITY), reverse=True)
        if preferred_estimator:
            estimators.insert(0, estimators.pop(estimators.index(lambda e: e.plugin_info.name == preferred_estimator)))
        for estimator in estimators:
            estimate = estimator.estimate(entry)
            # return first successful estimation
            if estimate is not None:
                return estimate


@event('plugin.register')
def register_plugin():
    plugin.register(EstimateRelease, 'estimate_release', api_ver=2)
