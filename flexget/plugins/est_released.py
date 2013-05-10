import logging
from flexget.plugin import get_plugins_by_group
log = logging.getLogger('est_released')


# Helper funciton called by discover plugins
def estimate(task, entry):
    log.info(entry['title'])
    estimators = get_plugins_by_group('estimate_released')
    for estimator in estimators:
        # is_released returns estimated date of released for the entry, None if it can't figure it out
        est_date = estimator.instance.is_released(task, entry)
        if (est_date is not None):
            return est_date
