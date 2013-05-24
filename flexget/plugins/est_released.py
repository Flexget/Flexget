import logging
from flexget.plugin import get_plugins_by_group, register_plugin

log = logging.getLogger('est_released')


class EstimateRelease(object):

    """
    Front-end for estimator plugins that estimate release times
    for various things (series, movies).
    """

    def estimate(self, entry):
        """
        Estimate release schedule for Entry

        :param entry:
        :return: estimated date of released for the entry, None if it can't figure it out
        """

        log.info(entry['title'])
        estimators = get_plugins_by_group('estimate_release')
        for estimator in estimators:
            estimate = estimator.instance.estimate(entry)
            # return first successful estimation
            if estimate is not None:
                return estimate

register_plugin(EstimateRelease, 'estimate_release', api_ver=2)
