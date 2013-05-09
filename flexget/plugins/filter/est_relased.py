from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, get_plugins_by_group
from datetime import datetime
log = logging.getLogger('est_released')


class EstimateReleased(object):
    """
        Just accepts all entries.

        Example::

          accept_all: true
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    # Helper funciton called by discover plugins and by on_task_filter
    def estimate(self, task, entry):
        log.info(entry['title'])
        estimators = get_plugins_by_group('estimate_released')
        for estimator in estimators:
            # is_released can return None if it has no idea, True if released, False if not released
            est_date = estimator.instance.is_released(task, entry)
            if (est_date is not None):
                return est_date

    def on_task_filter(self, task, config):
        if config:
            for entry in self.filter_helper(task, task.entries, config):
                est_date = self.estimate(task, entry)
                if (est_date is not None and datetime.now().date() >= est_date):
                    entry.accept()

register_plugin(EstimateReleased, 'est_released', api_ver=2)
