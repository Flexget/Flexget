from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='est_released')


class EstimateRelease:
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

        logger.debug(entry['title'])
        estimators = [
            e.instance.estimate for e in plugin.get_plugins(interface='estimate_release')
        ]
        for estimator in sorted(
            estimators, key=lambda e: getattr(e, 'priority', plugin.PRIORITY_DEFAULT), reverse=True
        ):
            estimate = estimator(entry)
            # return first successful estimation
            if estimate is not None:
                return estimate


@event('plugin.register')
def register_plugin():
    plugin.register(EstimateRelease, 'estimate_release', api_ver=2, interfaces=[])
