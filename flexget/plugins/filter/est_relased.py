from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, get_plugins_by_group

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
    def filter_helper(self, task, arg_entries, config):
        entries = []
        for entry in arg_entries:
            log.info(entry['title'])
            estimators = get_plugins_by_group('estimate_released')
            for estimator in estimators:
                # is_released can return None if it has no idea, True if released, False if not released
                res = estimator.instance.is_released(task, entry)
                if (res is None):
                    continue
                elif (res is False):
                    break
                elif (res is True):
                    entries.append(entry)
                    break
        return entries

    def on_task_filter(self, task, config):
        if config:
            for entry in self.filter_helper(task, task.entries, config):
                entry.accept()

register_plugin(EstimateReleased, 'est_released', api_ver=2)
